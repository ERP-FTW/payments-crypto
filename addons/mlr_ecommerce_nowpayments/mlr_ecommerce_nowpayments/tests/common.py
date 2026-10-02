import json
from unittest.mock import patch

from odoo.addons.payment.tests.common import PaymentCommon


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


class FakeNowPayments:
    """In-process stand-in for the NOWPayments REST API.

    It records every outbound call (method, url, headers, json body) so tests can assert what Odoo
    actually sent, and answers from the ``payments`` and ``invoices`` dictionaries. It never
    reaches the network: a test that passes here proves Odoo's handling, not the provider.
    """

    JWT = 'jwt-token-SECRET-123'

    def __init__(self):
        self.calls = []
        self.payments = {}  # payment_id -> payment dict as GET /v1/payment/{id} returns it
        self.payment_lookup_failure = None  # an HTTP status or an exception for GET /v1/payment/{id}
        self.next_invoice_id = 5000

    def _record(self, method, url, headers=None, json_body=None):
        self.calls.append({
            'method': method.upper(),
            'url': url,
            'headers': dict(headers or {}),
            'json': json_body,
        })

    def request(self, method, url, headers=None, json=None, data=None, timeout=None, **kwargs):
        body = json if json is not None else (__import__('json').loads(data) if data else None)
        self._record(method, url, headers, body)
        path = url.split('://', 1)[-1].split('/', 1)[-1]
        path = '/' + path
        if method.upper() == 'POST' and path.startswith('/v1/auth'):
            return FakeResponse(200, {'token': self.JWT})
        if method.upper() == 'POST' and path.startswith('/v1/invoice'):
            self.next_invoice_id += 1
            invoice_id = str(self.next_invoice_id)
            return FakeResponse(200, {
                'id': invoice_id,
                'order_id': body.get('order_id'),
                'price_amount': str(body.get('price_amount')),
                'price_currency': body.get('price_currency'),
                'invoice_url': f'https://nowpayments.io/payment/?iid={invoice_id}',
            })
        if method.upper() == 'GET' and (path.startswith('/v1/payment/?') or path.startswith('/v1/payment?')):
            query = path.split('?', 1)[1]
            params = dict(p.split('=', 1) for p in query.split('&') if '=' in p)
            data_rows = list(self.payments.values())
            if 'invoiceId' in params:
                data_rows = [p for p in data_rows if str(p.get('invoice_id')) == params['invoiceId']]
            data_rows.sort(key=lambda p: p.get('created_at', ''), reverse=True)
            limit = int(params.get('limit', 10))
            page = int(params.get('page', 0))
            window = data_rows[page * limit:(page + 1) * limit]
            return FakeResponse(200, {'data': window, 'limit': limit, 'page': page, 'total': len(data_rows)})
        if method.upper() == 'GET' and path.startswith('/v1/payment/'):
            failure = self.payment_lookup_failure
            if isinstance(failure, Exception):
                raise failure
            if failure:
                return FakeResponse(failure, {'message': 'temporarily unavailable'})
            payment_id = path[len('/v1/payment/'):].strip('/')
            if payment_id in self.payments:
                return FakeResponse(200, self.payments[payment_id])
            return FakeResponse(404, {'message': 'not found'})
        if method.upper() == 'GET' and path.startswith('/v1/status'):
            return FakeResponse(200, {'message': 'OK'})
        if method.upper() == 'GET' and path.startswith('/v1/currencies'):
            return FakeResponse(200, {'currencies': ['btc']})
        return FakeResponse(404, {'message': f'unhandled {method} {path}'})

    def get(self, url, headers=None, **kwargs):
        return self.request('GET', url, headers=headers, **kwargs)

    def post(self, url, headers=None, json=None, data=None, **kwargs):
        return self.request('POST', url, headers=headers, json=json, data=data, **kwargs)

    def calls_to(self, fragment, method=None):
        return [
            c for c in self.calls
            if fragment in c['url'] and (method is None or c['method'] == method.upper())
        ]


class NowPaymentsCommon(PaymentCommon):

    API_KEY = 'np-api-key-SECRET-A'
    PASSWORD = 'np-password-SECRET'
    IPN_SECRET = 'np-ipn-secret-SECRET'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency = cls.currency_usd
        cls.provider = cls._prepare_provider('now', update_values={
            'is_crypto_provider': True,
            'crypto_server_url': 'https://api-sandbox.nowpayments.io',
            'crypto_api_key': cls.API_KEY,
            'nowpayments_username': 'ops@example.com',
            'nowpayments_password': cls.PASSWORD,
            'crypto_min_amount': 1.0,
            'crypto_max_amount': 10000.0,
            'available_currency_ids': [(6, 0, cls.currency_usd.ids)],
        })
        if 'nowpayments_ipn_secret' in cls.provider._fields:
            cls.provider.nowpayments_ipn_secret = cls.IPN_SECRET
        cls.payment_method = cls.provider.payment_method_ids[:1]
        cls.payment_method_id = cls.payment_method.id
        cls.amount = 100.0
        cls.reference = 'NP-TEST-0001'

    def setUp(self):
        super().setUp()
        self.fake = FakeNowPayments()
        for target in ('requests.request', 'requests.get', 'requests.post'):
            method = target.split('.')[-1]
            patcher = patch(target, side_effect=getattr(self.fake, method))
            self.startPatcher(patcher)

    def _provider_payment(self, tx, payment_id='4400001', status='finished', **overrides):
        payment = {
            'payment_id': int(payment_id),
            'invoice_id': int(tx.crypto_invoice_id) if tx.crypto_invoice_id else None,
            'payment_status': status,
            'pay_address': 'bc1qexampleaddress',
            'price_amount': tx.amount,
            'price_currency': tx.currency_id.name.lower(),
            'pay_amount': 0.0015,
            'actually_paid': 0.0015 if status in ('finished', 'confirmed', 'sending') else 0,
            'pay_currency': 'btc',
            'order_id': tx.reference,
            'order_description': tx.reference,
            'purchase_id': 777001,
            'outcome_amount': 0.0014,
            'outcome_currency': 'btc',
            'created_at': '2026-10-01T10:00:00.000Z',
            'updated_at': '2026-10-01T10:05:00.000Z',
        }
        payment.update(overrides)
        self.fake.payments[str(payment_id)] = payment
        return payment

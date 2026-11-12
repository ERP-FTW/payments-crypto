import json
import logging
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

API_KEY = 'btcpay-api-key-SECRET'


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeGreenfield:
    """Answers like BTCPay Server's Greenfield API (per its OpenAPI definition)."""

    def __init__(self):
        self.calls = []
        self.status_code = 200

    def __call__(self, method=None, url=None, headers=None, data=None, timeout=None, **kwargs):
        body = json.loads(data) if data else None
        self.calls.append({'method': method, 'url': url, 'headers': dict(headers or {}), 'json': body, 'timeout': timeout})
        if self.status_code != 200:
            return _Response(self.status_code, {'message': 'error'})
        if '/rates' in url:
            return _Response(200, [
                {'currencyPair': 'BTC_EUR', 'rate': '50000.00', 'errors': []},
                {'currencyPair': 'BTC_USD', 'rate': '60000.00', 'errors': []},
            ])
        if url.endswith('/lightning/BTC/invoices') and method == 'POST':
            return _Response(200, {'id': 'ln1', 'BOLT11': 'lnbc1', 'amount': body['amount'], 'status': 'Unpaid'})
        if url.endswith('/invoices/') and method == 'POST':
            return _Response(200, {'id': 'inv1', 'checkoutLink': 'https://btcpay.example/i/inv1', 'status': 'New'})
        if '/lightning/BTC/invoices/' in url:
            return _Response(200, {'id': 'ln1', 'status': 'Paid'})
        if '/invoices/' in url:
            return _Response(200, {'id': 'inv1', 'status': 'Settled'})
        return _Response(404, {})


@tagged('post_install', '-at_install', 'btcpay')
class TestBTCPayContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.currency_id = cls.env.ref('base.USD')
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'BTCPay', 'use_payment_terminal': 'btcpay', 'company_id': cls.env.company.id,
            'server_url': 'https://btcpay.example', 'api_key': API_KEY, 'btcpay_store_id': 'STORE1',
            'btcpay_payment_flow': 'payment link', 'btcpay_selected_crypto': 'lightning',
            'btcpay_expiration_minutes': 15, 'btcpay_company_name': 'Shop',
            'crypto_minimum_amount': 0.0, 'crypto_maximum_amount': 10000.0,
        })

    def setUp(self):
        super().setUp()
        self.fake = FakeGreenfield()
        patcher = patch('odoo.addons.mlr_pos_btcpay.models.pos_payment_method.requests.request', side_effect=self.fake)
        self.startPatcher(patcher)

    def _create(self, flow):
        self.method.btcpay_payment_flow = flow
        return self.env['pos.payment.method'].btcpay_create_crypto_invoice(
            {'pm_id': self.method.id, 'amount': 30.0, 'order_id': 'ORDER-1'})

    def test_rate_is_read_for_the_company_currency_pair(self):
        result = self._create('payment link')
        rates = [c for c in self.fake.calls if '/rates' in c['url']][0]
        self.assertIn('currencyPair=BTC_USD', rates['url'])
        # 30 USD at 60000 USD/BTC = 50000 sats; the first row (EUR) would give 60000.
        self.assertEqual(result.get('crypto_amt'), 50000.0)

    def test_payment_link_expiry_is_sent_in_minutes(self):
        self._create('payment link')
        invoice = [c for c in self.fake.calls if c['url'].endswith('/invoices/')][0]
        self.assertEqual(invoice['json']['checkout']['expirationMinutes'], 15)

    def test_lightning_invoice_amount_is_a_millisatoshi_string_and_expiry_in_seconds(self):
        self._create('direct invoice')
        invoice = [c for c in self.fake.calls if c['url'].endswith('/lightning/BTC/invoices')][0]
        self.assertEqual(invoice['json']['amount'], '50000000')
        self.assertEqual(invoice['json']['expiry'], 900)

    def test_api_key_never_reaches_the_log(self):
        with self.assertLogs('odoo.addons.mlr_pos_btcpay', level=logging.DEBUG) as captured:
            logging.getLogger('odoo.addons.mlr_pos_btcpay').debug('capture')
            self._create('payment link')
            self._create('direct invoice')
            self.env['pos.payment.method'].btcpay_check_payment_status(
                {'pm_id': self.method.id, 'invoice_id': 'inv1', 'order_id': 'ORDER-1'})
        self.assertNotIn(API_KEY, '\n'.join(captured.output))

    def test_failed_status_check_returns_a_status_for_both_flows(self):
        self.fake.status_code = 500
        for flow in ('payment link', 'direct invoice'):
            self.method.btcpay_payment_flow = flow
            result = self.env['pos.payment.method'].btcpay_check_payment_status(
                {'pm_id': self.method.id, 'invoice_id': 'inv1', 'order_id': 'ORDER-1'})
            self.assertEqual(result.get('status'), 'inaccessible', (flow, result))

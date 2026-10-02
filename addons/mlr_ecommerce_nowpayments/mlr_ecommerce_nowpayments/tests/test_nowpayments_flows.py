import hashlib
import hmac
import json
import logging
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.payment.tests.http_common import PaymentHttpCommon

from .common import NowPaymentsCommon


def _sign(secret, body):
    """Sign a notification body the way NOWPayments does (see test_nowpayments_signature)."""
    try:
        from odoo.addons.mlr_ecommerce_nowpayments.controllers.main import nowpayments_signature
    except ImportError:  # the module predates notification support
        def sort_object(value):
            if isinstance(value, dict):
                return {k: sort_object(value[k]) for k in sorted(value)}
            return value
        message = json.dumps(sort_object(body), separators=(',', ':'), ensure_ascii=False)
        return hmac.new(secret.encode(), message.encode(), hashlib.sha512).hexdigest()
    return nowpayments_signature(secret, body)


@tagged('post_install', '-at_install', 'nowpayments')
class TestNowPaymentsFlows(NowPaymentsCommon, PaymentHttpCommon):

    # --- Invoice creation: identity, amount and currency come from the Odoo transaction ----------

    def _create_invoice(self, tx, **posted):
        data = {'reference': tx.reference, 'amount': tx.amount, 'currency_id': tx.currency_id.name}
        data.update(posted)
        url = self._build_url('/payment/now/createInvoice')
        return self.opener.post(url, data=self._format_http_request_payload(data), allow_redirects=False)

    def test_invoice_uses_transaction_amount_and_currency_not_posted_values(self):
        tx = self._create_transaction('redirect')
        # A tampered checkout form posts a different amount and currency.
        self._create_invoice(tx, amount='1.00', currency_id='EUR')
        invoice_calls = self.fake.calls_to('/v1/invoice', 'POST')
        self.assertEqual(len(invoice_calls), 1)
        payload = invoice_calls[0]['json']
        self.assertEqual(float(payload['price_amount']), 100.0)
        self.assertEqual(payload['price_currency'].upper(), 'USD')
        self.assertEqual(payload['order_id'], tx.reference)
        self.assertTrue(tx.crypto_invoice_id)

    def test_invoice_requests_callback_and_is_reused_on_resubmit(self):
        tx = self._create_transaction('redirect')
        # A website domain comes back with a trailing slash.
        with patch.object(type(self.env['payment.provider']), 'get_base_url',
                          return_value='https://shop.example.com/'):
            self._create_invoice(tx)
            self._create_invoice(tx)
        invoice_calls = self.fake.calls_to('/v1/invoice', 'POST')
        self.assertEqual(len(invoice_calls), 1, "a resubmitted checkout must not open a second invoice")
        callback = invoice_calls[0]['json'].get('ipn_callback_url', '')
        self.assertTrue(callback.endswith('/payment/now/ipn'))
        self.assertEqual(callback, 'https://shop.example.com/payment/now/ipn')

    def test_invoice_uses_the_transaction_provider_of_its_company(self):
        company_b = self.env['res.company'].create({'name': 'NOWPayments Company B'})
        provider_b = self._prepare_provider('now', company=company_b, update_values={
            'is_crypto_provider': True,
            'crypto_server_url': 'https://api-sandbox.nowpayments.io',
            'crypto_api_key': 'np-api-key-SECRET-B',
            'crypto_min_amount': 1.0,
            'crypto_max_amount': 10000.0,
        })
        tx_a = self._create_transaction('redirect', reference='NP-COMPANY-A')
        tx_b = self._create_transaction('redirect', provider_id=provider_b.id, company_id=company_b.id,
                                        reference='NP-COMPANY-B')
        self._create_invoice(tx_a)
        self._create_invoice(tx_b)
        invoice_calls = self.fake.calls_to('/v1/invoice', 'POST')
        self.assertEqual(len(invoice_calls), 2)
        keys = {call['json']['order_id']: call['headers'].get('x-api-key') for call in invoice_calls}
        self.assertEqual(keys, {'NP-COMPANY-A': self.API_KEY, 'NP-COMPANY-B': 'np-api-key-SECRET-B'})

    # --- Completion: verified provider state, not the browser or the callback body -------------

    def _ipn(self, body, secret=None, signature=None):
        sig = signature if signature is not None else _sign(secret or self.IPN_SECRET, body)
        url = self._build_url('/payment/now/ipn')
        return self.opener.post(url, data=json.dumps(body), allow_redirects=False, headers={
            'Content-Type': 'application/json', 'x-nowpayments-sig': sig,
        })

    def _ipn_body(self, payment):
        body = dict(payment)
        body['fee'] = {'currency': 'btc', 'depositFee': 0, 'withdrawalFee': 0, 'serviceFee': 0}
        return body

    def test_ipn_with_invalid_signature_is_refused(self):
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        payment = self._provider_payment(tx)
        response = self._ipn(self._ipn_body(payment), signature='0' * 128)
        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(tx.state, 'done')

    def test_ipn_completes_without_the_buyer_returning(self):
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        payment = self._provider_payment(tx, payment_id='4400001', status='finished')
        response = self._ipn(self._ipn_body(payment))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, '4400001')
        # The status was re-read from the provider, not taken from the callback body.
        self.assertTrue(self.fake.calls_to('/v1/payment/4400001', 'GET'))

    def test_ipn_is_not_acknowledged_while_the_provider_cannot_confirm_it(self):
        import requests
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        payment = self._provider_payment(tx, payment_id='4400009', status='finished')
        for failure in (503, 429, requests.exceptions.ConnectTimeout('timed out')):
            with self.subTest(failure=failure):
                self.fake.payment_lookup_failure = failure
                response = self._ipn(self._ipn_body(payment))
                self.assertEqual(response.status_code, 503, "a retryable answer, so NOWPayments sends it again")
                self.assertNotEqual(tx.state, 'done')
        self.fake.payment_lookup_failure = None
        response = self._ipn(self._ipn_body(payment))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(tx.state, 'done')

    def test_ipn_for_a_payment_the_provider_does_not_know_is_acknowledged(self):
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        payment = self._provider_payment(tx, payment_id='4400010', status='finished')
        del self.fake.payments['4400010']  # NOWPayments answers 404: retrying cannot change that
        response = self._ipn(self._ipn_body(payment))
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(tx.state, 'done')

    def test_invoice_creation_holds_the_transaction_row_lock(self):
        tx = self._create_transaction('redirect')
        invoices_opened_at_lock = []
        cursor_class = type(self.env.cr)
        original_execute = cursor_class.execute

        def execute(cr, query, params=None, log_exceptions=True):
            text = str(getattr(query, 'code', query))
            if 'FOR UPDATE' in text and 'payment_transaction' in text:
                invoices_opened_at_lock.append(len(self.fake.calls_to('/v1/invoice', 'POST')))
            return original_execute(cr, query, params, log_exceptions)

        with patch.object(cursor_class, 'execute', execute):
            tx._nowpayments_get_invoice_url()
        # The row is locked before the invoice is opened, so a concurrent checkout of the same
        # transaction waits and then finds the invoice instead of opening its own.
        self.assertEqual(invoices_opened_at_lock, [0])
        self.assertEqual(len(self.fake.calls_to('/v1/invoice', 'POST')), 1)

    def test_callback_body_cannot_override_provider_amount(self):
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        # The provider says this payment is for 1.00 USD; the (validly signed) callback claims 100.
        payment = self._provider_payment(tx, status='finished', price_amount=1.0)
        body = self._ipn_body(payment)
        body['price_amount'] = 100.0
        self._ipn(body)
        self.assertNotEqual(tx.state, 'done')
        self.assertIn('amount', (tx.state_message or '').lower())

    def test_payment_of_another_order_does_not_change_state(self):
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        payment = self._provider_payment(tx, status='finished', order_id='SOMEONE-ELSE')
        body = self._ipn_body(payment)
        body['order_id'] = tx.reference
        self._ipn(body)
        self.assertEqual(tx.state, 'draft')
        self.assertFalse(tx.provider_reference)

    def test_duplicate_notifications_post_one_payment(self):
        if not hasattr(self, 'post_process_patcher'):
            self.skipTest("account_payment is not installed")
        self.post_process_patcher.stop()  # exercise the real accounting post-processing
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        payment = self._provider_payment(tx, status='finished')
        for _i in range(3):
            self._ipn(self._ipn_body(payment))
        self.env['payment.transaction']._cron_nowpayments_reconcile()
        tx._post_process()
        tx._post_process()
        self.assertEqual(tx.state, 'done')
        payments = self.env['account.payment'].search([('payment_transaction_id', '=', tx.id)])
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments.amount, tx.amount)
        self.assertEqual(payments.currency_id, tx.currency_id)

    def test_delayed_confirmation_is_reconciled_by_the_scheduled_job(self):
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        self._provider_payment(tx, payment_id='4400002', status='confirming')
        self.env['payment.transaction']._cron_nowpayments_reconcile()
        self.assertEqual(tx.state, 'pending')
        self._provider_payment(tx, payment_id='4400002', status='finished')
        self.env['payment.transaction']._cron_nowpayments_reconcile()
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, '4400002')

    def test_return_finds_payment_beyond_the_ten_most_recent(self):
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        self._provider_payment(tx, payment_id='4400003', status='finished',
                               created_at='2026-09-01T00:00:00.000Z')
        for i in range(12):  # newer payments of other orders on the same account
            self.fake.payments[str(5500000 + i)] = {
                'payment_id': 5500000 + i, 'invoice_id': 9, 'payment_status': 'finished',
                'order_id': f'OTHER-{i}', 'price_amount': 5, 'price_currency': 'usd',
                'created_at': f'2026-10-0{1 + i % 9}T00:00:00.000Z',
            }
        self.opener.get(self._build_url('/payment/now/return'), params={'ref': tx.reference},
                        allow_redirects=False)
        self.assertEqual(tx.state, 'done')

    def test_partial_payment_is_not_confirmed(self):
        tx = self._create_transaction('redirect')
        self._create_invoice(tx)
        payment = self._provider_payment(tx, status='partially_paid', actually_paid=0.0005)
        self._ipn(self._ipn_body(payment))
        self.assertNotEqual(tx.state, 'done')

    def test_no_secret_reaches_the_log(self):
        tx = self._create_transaction('redirect')
        with self.assertLogs('odoo.addons.mlr_ecommerce_nowpayments', level=logging.DEBUG) as captured:
            logging.getLogger('odoo.addons.mlr_ecommerce_nowpayments').debug('log capture started')
            self._create_invoice(tx)
            self._provider_payment(tx, status='finished')
            self.env['payment.transaction']._cron_nowpayments_reconcile()
        text = '\n'.join(captured.output)
        for secret in (self.API_KEY, self.PASSWORD, self.IPN_SECRET, self.fake.JWT):
            self.assertNotIn(secret, text)

import json
import logging
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


API_KEY = "now-api-key-SECRET"
PASSWORD = "now-password-SECRET"
TOKEN = "now-bearer-token-SECRET"
RESPONSE_SECRET = "provider-response-SECRET"


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeNowPayments:
    """Deterministic NOWPayments stand-in; no provider network is contacted."""

    def __init__(self):
        self.calls = []
        self.auth_status = 200
        self.status_code = 200
        self.payment_status = "waiting"

    def _call(self, method, url, headers, data=None):
        body = json.loads(data) if data else None
        self.calls.append({
            "method": method,
            "url": url,
            "headers": dict(headers or {}),
            "json": body,
        })
        if url.endswith("/v1/auth"):
            payload = (
                {"token": TOKEN, "diagnostic": RESPONSE_SECRET}
                if self.auth_status == 200
                else {"message": RESPONSE_SECRET}
            )
            return _Response(self.auth_status, payload)
        if self.status_code != 200:
            return _Response(self.status_code, {"message": RESPONSE_SECRET})
        payment = {
            "payment_status": self.payment_status,
            "payment_id": "PAY-1",
            "order_id": "ORDER-1",
            "pay_amount": 0.001,
            "pay_currency": "btc",
        }
        if "/v1/payment/?" in url:
            return _Response(200, {"data": [payment]})
        if "/v1/payment/PAY-1" in url:
            return _Response(200, payment)
        return _Response(404, {"message": RESPONSE_SECRET})

    def get(self, url, headers=None, **kwargs):
        return self._call("GET", url, headers)

    def post(self, url, data=None, headers=None, **kwargs):
        return self._call("POST", url, headers, data)


@tagged("post_install", "-at_install", "nowpayments_pos")
class TestNowPaymentsContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.method = cls.env["pos.payment.method"].create({
            "name": "NOWPayments",
            "use_payment_terminal": "now",
            "company_id": cls.env.company.id,
            "server_url": "https://api-sandbox.nowpayments.example",
            "api_key": API_KEY,
            "nowpayments_username": "pos@example.invalid",
            "nowpayments_password": PASSWORD,
            "now_payment_flow": "direct invoice",
            "now_selected_crypto": "btc",
            "crypto_minimum_amount": 0.0,
            "crypto_maximum_amount": 10000.0,
        })

    def setUp(self):
        super().setUp()
        self.fake = FakeNowPayments()
        self.startPatcher(patch(
            "odoo.addons.mlr_pos_nowpayments.models.pos_payment_method.requests.get",
            side_effect=self.fake.get,
        ))
        self.startPatcher(patch(
            "odoo.addons.mlr_pos_nowpayments.models.pos_payment_method.requests.post",
            side_effect=self.fake.post,
        ))

    def _status(self, flow):
        self.method.now_payment_flow = flow
        return self.env["pos.payment.method"].now_check_payment_status({
            "pm_id": self.method.id,
            "invoice_id": "PAY-1",
            "order_id": "ORDER-1",
        })

    def test_all_provider_states_are_preserved_for_both_flows(self):
        states = (
            "finished", "waiting", "confirming", "confirmed", "sending",
            "expired", "failed", "partially_paid", "refunded",
        )
        for flow in ("direct invoice", "payment link"):
            for state in states:
                with self.subTest(flow=flow, state=state):
                    self.fake.payment_status = state
                    self.assertEqual(self._status(flow).get("payment_status"), state)

    def test_inaccessible_status_is_stable_for_both_flows(self):
        self.fake.status_code = 503
        for flow in ("direct invoice", "payment link"):
            with self.subTest(flow=flow):
                self.assertEqual(
                    self._status(flow),
                    {"payment_status": "inaccessible"},
                )

    def test_repeated_polling_is_idempotent(self):
        self.fake.payment_status = "finished"
        for flow in ("direct invoice", "payment link"):
            with self.subTest(flow=flow):
                first = self._status(flow)
                second = self._status(flow)
                self.assertEqual(first, second)
                self.assertEqual(first["payment_id"], "PAY-1")

    def test_auth_failure_is_sanitized(self):
        self.fake.auth_status = 401
        with self.assertRaises(UserError) as raised:
            self.method.call_cryptopay_api({}, "/v1/sub-partner", "GET", 1)
        self.assertNotIn(PASSWORD, str(raised.exception))
        self.assertNotIn(API_KEY, str(raised.exception))
        self.assertNotIn(TOKEN, str(raised.exception))

    def test_credentials_payload_headers_and_response_never_reach_logs(self):
        with self.assertLogs(
            "odoo.addons.mlr_pos_nowpayments", level=logging.INFO
        ) as captured:
            logging.getLogger("odoo.addons.mlr_pos_nowpayments").info("capture")
            self.method.call_cryptopay_api({}, "/v1/sub-partner", "GET", 1)
            self._status("direct invoice")
        output = "\n".join(captured.output)
        for secret in (API_KEY, PASSWORD, TOKEN, RESPONSE_SECRET):
            self.assertNotIn(secret, output)
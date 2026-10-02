import hashlib
import hmac

from odoo.tests import BaseCase, tagged

from odoo.addons.mlr_ecommerce_nowpayments.controllers.main import (
    nowpayments_signature,
    nowpayments_signed_message,
)


@tagged('post_install', '-at_install', 'nowpayments')
class TestNowPaymentsSignature(BaseCase):

    def test_message_matches_the_reference_javascript_serialization(self):
        body = {
            'payment_id': 5077125051,
            'price_amount': 100.0,
            'pay_amount': 0.00153,
            'order_id': 'S00042-1',
            'fee': {'serviceFee': 0, 'currency': 'btc', 'depositFee': 1.5e-07},
            'payment_status': 'finished',
            'order_description': 'Café',
        }
        # What JSON.stringify(sortObject(body)) produces in the provider's reference code.
        expected = (
            '{"fee":{"currency":"btc","depositFee":1.5e-7,"serviceFee":0},'
            '"order_description":"Café","order_id":"S00042-1","pay_amount":0.00153,'
            '"payment_id":5077125051,"payment_status":"finished","price_amount":100}'
        )
        self.assertEqual(nowpayments_signed_message(body), expected)
        self.assertEqual(
            nowpayments_signature('secret', body),
            hmac.new(b'secret', expected.encode(), hashlib.sha512).hexdigest(),
        )

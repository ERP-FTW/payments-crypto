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

    def test_numbers_are_printed_as_javascript_prints_them(self):
        # Crypto amounts often fall between 1e-6 and 1e-4, where Python's repr switches to
        # exponential notation and JavaScript does not. Expected values are Node's JSON.stringify.
        body = {
            'actually_paid': 0.0000012, 'outcome_amount': 0.00005, 'network_fee': 1e-7,
            'rate': 1.2345678901234568e20, 'big': 2 ** 60, 'zero': -0.0, 'tiny': 1e-6,
        }
        self.assertEqual(
            nowpayments_signed_message(body),
            '{"actually_paid":0.0000012,"big":1152921504606847000,"network_fee":1e-7,'
            '"outcome_amount":0.00005,"rate":123456789012345680000,"tiny":0.000001,"zero":0}',
        )

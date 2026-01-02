# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from odoo import api, models, fields
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    btcpay_invoice_id = fields.Char('BTCPay Invoice ID')
    btcpay_conversion_rate = fields.Float('Conversion rate')
    btcpay_invoiced_sat_amount = fields.Float('Invoiced Satoshi Amount', digits=(12, 8))
    btcpay_payment_link = fields.Char('BTCPay Payment Link')
    btcpay_payment_link_qr_code = fields.Binary('QR Code', compute="_generate_qr")


    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Paypal-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'btcpay':
            return res

        base_url = self.provider_id.get_base_url()
        return {
            'reference': self.reference,
            'amount': self.amount,
            'currency_code': self.currency_id.name,
        }

    def action_get_conversion_rate(self):
        try:
            record_search = self.env['payment.provider'].search([('code', '=', 'btcpay')])
            base_url = record_search.mapped('btcpay_server_url')[0]
            store_id = record_search.mapped('btcpay_store_id')[0]
            api_key = record_search.mapped('btcpay_api_key')[0]
            server_url = base_url + "/api/v1/stores/" + store_id + "/rates"
            headers = {"Authorization": "Token %s" % (api_key)}
            response = requests.request(method="GET", url=server_url, headers=headers)
            response_json = response.json()
            result = response_json[0]['rate'] if response.status_code == 200 else None
            return result
        except Exception as e:
            raise UserError(_("Get Conversion Rate: %s", e.args))

    def get_amount_sats(self, pos_payment_obj):
        try:
            btcpay_conversion_rate = self.action_get_conversion_rate()
            amount_sats = round((float(pos_payment_obj.get('amount')) / float(btcpay_conversion_rate)) * 100000000, 1)
            invoiced_info = {'conversion_rate': btcpay_conversion_rate,
                             'invoiced_sat_amount': amount_sats
                             }
            return invoiced_info
        except Exception as e:
            raise UserError(_("Get Millisat amount: %s", e.args))


    def action_create_invoice_lightning(self, pos_payment_obj):
        try:
            record_search = self.env['payment.provider'].search([('code', '=', 'btcpay')])
            base_url = record_search.mapped('btcpay_server_url')[0]
            store_id = record_search.mapped('btcpay_store_id')[0]
            api_key = record_search.mapped('btcpay_api_key')[0]
            expiration_minutes = record_search.mapped('btcpay_expiration_minutes')[0]
            invoiced_info = self.get_amount_sats(pos_payment_obj)
            amount_millisats = invoiced_info['invoiced_sat_amount'] * 1000
            server_url = base_url + "/api/v1/stores/" + store_id + "/lightning/BTC/invoices"
            headers = {"Authorization": "Token %s" % (api_key), "Content-Type": "application/json"}
            print(pos_payment_obj)
            payload = {
                "amount": amount_millisats,
                #"description": self.btcpay_company_name + " " + pos_payment_obj.get('order_name'),
                "expiry": expiration_minutes,
            }
            response = requests.post(server_url, data=json.dumps(payload), headers=headers)
            response_json = response.json()
            result = response_json if response.status_code == 200 else None
            result.update(invoiced_info)
            return result
        except Exception as e:
            raise UserError(_("Create BTCPay Invoice: %s", e.args))
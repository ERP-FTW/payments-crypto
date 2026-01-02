
import logging
import uuid

import requests
from werkzeug.urls import url_encode, url_join, url_parse

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('btcpay', "btcpay")], ondelete={'btcpay': 'set default'})
    btcpay_store_id = fields.Char(string='Store ID')

    def btcpay_test_server_connection(self):
        try:
            server_url = self.crypto_server_url + "/api/v1/health"
            headers = {"Authorization": f"Token {self.crypto_api_key}",
            "Content-Type": "application/json"}
            response = requests.request(method="GET", url=server_url, headers=headers)
            is_success = True if response.status_code == 200 else False
            return is_success
        except Exception as e:
            raise UserError(_("Test Connection Error: %s", e.args))

    def btcpay_action_test_connection(self):
        is_success = self.btcpay_test_server_connection()
        type = (
            "success"
            if is_success
            else "danger"
        )
        messages = (
            "Everything seems properly set up!"
            if is_success
            else "Server credential is wrong. Please check credential."
        )
        title = _("Connection Testing")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": messages,
                "sticky": False,
                "type": type
            },
        }


    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'btcpay':
            return default_codes
        return ['btcpay']

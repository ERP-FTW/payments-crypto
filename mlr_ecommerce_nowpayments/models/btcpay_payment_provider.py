
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
    btcpay_server_url = fields.Char(string='Server URL')
    btcpay_api_key = fields.Char(string='API Key')
    nowpayments_username = fields.Char(string="NowPayments Username")
    nowpayments_password = fields.Char(string="NowPayments Password")
    btcpay_store_id = fields.Char(string='Store ID')
    btcpay_expiration_minutes = fields.Integer('Expiration Minutes')
    btcpay_monitoring_minutes = fields.Integer('Monitoring Minutes')
    btcpay_speed_policy = fields.Selection(
        [("HighSpeed", "HighSpeed"), ("MediumSpeed", "MediumSpeed"), ("LowMediumSpeed", "LowMediumSpeed"),
         ("LowSpeed", "LowSpeed")],
        default="HighSpeed",
        string="Speed Policy",
    )

    def test_btcpay_server_connection(self):
        try:
            server_url = self.btcpay_server_url + "/v1/currencies?fixed_rate=false"
            headers = {"x-api-key": (self.btcpay_api_key)}
            response = requests.request(method="GET", url=server_url, headers=headers)
            is_success = True if response.status_code == 200 else False
            return is_success
        except Exception as e:
            raise UserError(_("Test Connection Error: %s", e.args))

    def action_test_connection(self):
        is_success = self.test_btcpay_server_connection()
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


    def action_activate(self):
#        is_success = self.test_btcpay_server_connection()
#        if is_success:
#            # Get Conversion Rate
#            self.state = 'enabled'
            # Auto create Account Journal and POS Payment Method at the first Activate
        journal = self.env['account.journal'].search(
                [("use_btcpay_server", "=", True), ("type", "=", "bank"), ('company_id', '=', self.env.company.id)],
                limit=1)
#            if not journal:
        journal = self.env['account.journal'].search(
                    [("type", "=", "bank"), ('company_id', '=', self.env.company.id)], limit=1)
        new_btcpay_server_journal = journal.copy()
        new_btcpay_server_journal.write({
                    'name': 'BTCPay Server3',
                    'code': 'BTCP3',
                    'btcpay_server_instance_id': 100
                })
#        new_btcpay_server_pos_payment_method = self.env['pos.payment.method'].create({
#                    'name': 'BTCPay Server',
#                    'company_id': self.env.company.id,
#                    'journal_id': new_btcpay_server_journal.id
#                }
#                )
#        new_btcpay_server_pos_payment_method = self.env['pos.payment.method'].create({
#                    'name': 'BTCPay Server (Lightning)',
#                    'company_id': self.env.company.id,
#                    'journal_id': new_btcpay_server_journal.id
#                }
#                )
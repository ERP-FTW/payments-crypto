import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(
        selection_add=[("now", "now")], ondelete={"now": "set default"}
    )
    nowpayments_username = fields.Char(string="NowPayments Username")
    nowpayments_password = fields.Char(string="NowPayments Password")
    # now_store_id = fields.Char(string="Store ID")

    @api.constrains("code", "journal_id", "state")
    def _check_nowpayments_accounting_setup(self):
        for provider in self:
            if provider.code != "now" or provider.state not in ("enabled", "test"):
                continue
            journal = provider.journal_id
            if not journal:
                raise ValidationError(
                    _(
                        "NowPayments providers must define a journal before processing payments."
                    )
                )
            if not journal.inbound_payment_method_line_ids:
                raise ValidationError(
                    _(
                        "NowPayments journal '%s' must have at least one inbound payment method line."
                    )
                    % journal.display_name
                )

    def test_now_server_connection(self):
        try:
            server_url = self.crypto_server_url + "/v1/currencies?fixed_rate=false"
            headers = {"x-api-key": (self.crypto_api_key)}
            response = requests.request(method="GET", url=server_url, headers=headers)
            is_success = True if response.status_code == 200 else False
            return is_success
        except Exception as e:
            raise UserError(_("Test Connection Error: %s", e.args))

    def action_test_connection(self):
        is_success = self.test_now_server_connection()
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
                "type": type,
            },
        }

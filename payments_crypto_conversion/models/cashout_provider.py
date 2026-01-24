import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CryptoCashoutProvider(models.Model):
    _name = "crypto.cashout.provider"
    _description = "Crypto Cashout Provider"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Selection(
        selection=[("manual", "Manual")],
        required=True,
        default="manual",
        help="Technical provider code. Provider modules extend this selection.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()

    def provider_authenticate(self):
        self.ensure_one()
        raise UserError(
            _("Provider '%s' does not implement authentication.") % self.display_name
        )

    def provider_get_balance(self):
        self.ensure_one()
        raise UserError(
            _("Provider '%s' does not implement balance retrieval.")
            % self.display_name
        )

    def provider_create_payout(self, payout):
        self.ensure_one()
        if not payout:
            raise UserError(_("A payout record is required."))
        _logger.warning(
            "Provider %s does not implement payout creation for payout %s",
            self.display_name,
            payout.display_name,
        )
        raise UserError(
            _("Provider '%s' does not implement payout creation.")
            % self.display_name
        )

    def provider_get_payout(self, payout):
        self.ensure_one()
        if not payout:
            raise UserError(_("A payout record is required."))
        _logger.warning(
            "Provider %s does not implement payout refresh for payout %s",
            self.display_name,
            payout.display_name,
        )
        raise UserError(
            _("Provider '%s' does not implement payout status refresh.")
            % self.display_name
        )

    def action_test_connection(self):
        self.ensure_one()
        self.provider_authenticate()
        balance = self.provider_get_balance()
        message = _("Connection successful.")
        if balance:
            message = _("Connection successful. Balance retrieved.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Cashout Provider"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

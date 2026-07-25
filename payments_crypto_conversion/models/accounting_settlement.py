from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"
    settlement_id = fields.Many2one("crypto.settlement", copy=False, readonly=True, ondelete="restrict", check_company=True)


class AccountMove(models.Model):
    _inherit = "account.move"
    settlement_id = fields.Many2one("crypto.settlement", copy=False, readonly=True, ondelete="restrict", check_company=True)


class ResCurrencyMove(models.Model):
    _inherit = "res.currency.move"
    settlement_id = fields.Many2one("crypto.settlement", copy=False, readonly=True, ondelete="restrict", check_company=True)


class ResCurrencyMoveLine(models.Model):
    _inherit = "res.currency.move.line"
    settlement_id = fields.Many2one("crypto.settlement", copy=False, readonly=True, ondelete="restrict", check_company=True)

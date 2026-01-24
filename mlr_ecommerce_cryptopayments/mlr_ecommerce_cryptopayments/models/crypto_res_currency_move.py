# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCurrencyMove(models.Model):
    _inherit = "res.currency.move"

    payment_transaction_id = fields.Many2one(
        "payment.transaction",
        string="Payment Transaction",
        related="payment_id.payment_transaction_id",
        store=True,
        index=True,
        readonly=True,
    )


class ResCurrencyMoveLine(models.Model):
    _inherit = "res.currency.move.line"

    payment_transaction_id = fields.Many2one(
        "payment.transaction",
        string="Payment Transaction",
        related="move_id.payment_transaction_id",
        store=True,
        index=True,
        readonly=True,
    )

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_transaction_id = fields.Many2one(
        "payment.transaction",
        string="Payment Transaction",
        readonly=True,
        index=True,
        copy=False,
    )
    provider_invoice_id = fields.Char(string="Provider Invoice ID", copy=False)
    provider_payout_id = fields.Char(string="Provider Payout ID", copy=False)
    provider_payment_id = fields.Char(string="Provider Payment ID", copy=False)
    crypto_currency_id = fields.Many2one(
        "res.currency",
        string="Crypto Currency",
        copy=False,
    )
    crypto_amount = fields.Monetary(
        string="Crypto Amount",
        currency_field="crypto_currency_id",
        digits=(24, 12),
        copy=False,
    )
    crypto_rate = fields.Float(
        string="Crypto Rate",
        digits=(24, 12),
        copy=False,
    )
    crypto_payment_link = fields.Char(string="Crypto Payment Link", copy=False)

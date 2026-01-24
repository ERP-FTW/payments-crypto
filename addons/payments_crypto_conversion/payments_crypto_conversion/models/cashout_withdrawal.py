from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CryptoCashoutWithdrawal(models.Model):
    _name = "crypto.cashout.withdrawal"
    _description = "Crypto Cashout Withdrawal"
    _order = "id"

    payout_id = fields.Many2one(
        "crypto.cashout.payout",
        required=True,
        ondelete="cascade",
        index=True,
    )
    currency_code = fields.Char(required=True)
    currency_id = fields.Many2one("res.currency", string="Currency")
    amount = fields.Float(required=True)
    address = fields.Char(required=True)
    extra_id = fields.Char(string="Extra ID")
    provider_withdrawal_id = fields.Char(index=True)
    batch_withdrawal_id = fields.Char()
    status = fields.Char()
    tx_hash = fields.Char(string="Transaction Hash")
    error = fields.Text()
    created_at = fields.Datetime()
    requested_at = fields.Datetime()
    updated_at = fields.Datetime()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        currency_id = self.env.context.get("default_currency_id")
        if currency_id:
            currency = self.env["res.currency"].browse(currency_id)
            if currency and currency.exists():
                res.setdefault("currency_id", currency.id)
                res.setdefault("currency_code", self._normalize_currency_code(currency.name))
        return res

    @api.model
    def _normalize_currency_code(self, code):
        return (code or "").strip().upper()

    @api.model
    def _resolve_currency_from_code(self, code):
        normalized = self._normalize_currency_code(code)
        if not normalized:
            return self.env["res.currency"]
        return self.env["res.currency"].search([("name", "=", normalized)], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            code = self._normalize_currency_code(vals.get("currency_code"))
            vals["currency_code"] = code
            if code and not vals.get("currency_id"):
                currency = self._resolve_currency_from_code(code)
                if currency:
                    vals["currency_id"] = currency.id
        return super().create(vals_list)

    def write(self, vals):
        if "currency_code" in vals:
            code = self._normalize_currency_code(vals.get("currency_code"))
            vals["currency_code"] = code
            if code and not vals.get("currency_id"):
                currency = self._resolve_currency_from_code(code)
                if currency:
                    vals["currency_id"] = currency.id
        return super().write(vals)

    @api.constrains("amount")
    def _check_amount_positive(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Withdrawal amount must be strictly positive."))

    @api.constrains("currency_code", "currency_id", "payout_id")
    def _check_currency_matches_payout(self):
        for rec in self.filtered("payout_id"):
            payout_currency = rec.payout_id.crypto_currency_id
            if not payout_currency:
                continue
            expected_code = self._normalize_currency_code(payout_currency.name)
            if rec.currency_code and rec.currency_code != expected_code:
                raise ValidationError(
                    _(
                        "Withdrawal currency code %(code)s must match the payout currency %(expected)s."
                    )
                    % {"code": rec.currency_code, "expected": expected_code}
                )
            if rec.currency_id and rec.currency_id != payout_currency:
                raise ValidationError(
                    _("Withdrawal currency must match the payout crypto currency.")
                )

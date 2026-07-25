import uuid
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CryptoTransferLine(models.Model):
    _name = "crypto.transfer.line"
    _description = "Crypto Transfer Line"
    _order = "id"

    transfer_id = fields.Many2one(
        "crypto.transfer",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    currency_code = fields.Char(required=True)
    currency_id = fields.Many2one("res.currency", string="Currency")
    amount = fields.Float(required=True)
    atomic_amount = fields.Char(required=True, default="0", help="Exact non-negative quantity in the asset's smallest atomic unit.")
    external_idempotency_key = fields.Char(required=True, readonly=True, copy=False, index=True, default=lambda self: str(uuid.uuid4()))
    provider_transfer_id = fields.Char(readonly=True, copy=False, index=True)
    executed_at = fields.Datetime(readonly=True)
    executed_atomic_amount = fields.Char(readonly=True)
    verified_event_id = fields.Many2one("crypto.provider.event", readonly=True, ondelete="restrict")
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
        from .crypto_ledger import normalize_atomic
        for vals in vals_list:
            vals["atomic_amount"] = normalize_atomic(vals.get("atomic_amount", "0"))
            code = self._normalize_currency_code(vals.get("currency_code"))
            vals["currency_code"] = code
            if code and not vals.get("currency_id"):
                currency = self._resolve_currency_from_code(code)
                if currency:
                    vals["currency_id"] = currency.id
        return super().create(vals_list)

    def write(self, vals):
        if "external_idempotency_key" in vals:
            raise ValidationError(_("The external idempotency key is immutable."))
        if "provider_transfer_id" in vals:
            for line in self:
                if line.provider_transfer_id and vals["provider_transfer_id"] != line.provider_transfer_id:
                    raise ValidationError(_("A provider transfer ID cannot be replaced."))
        if "currency_code" in vals:
            code = self._normalize_currency_code(vals.get("currency_code"))
            vals["currency_code"] = code
            if code and not vals.get("currency_id"):
                currency = self._resolve_currency_from_code(code)
                if currency:
                    vals["currency_id"] = currency.id
        return super().write(vals)

    _sql_constraints = [
        ("line_provider_idempotency_uniq", "unique(transfer_id, external_idempotency_key)", "Transfer line idempotency keys must be unique."),
        ("line_provider_transfer_uniq", "unique(provider_transfer_id)", "The provider transfer ID is already linked."),
    ]

    @api.constrains("amount")
    def _check_amount_positive(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Withdrawal amount must be strictly positive."))

    @api.constrains("currency_code", "currency_id", "transfer_id")
    def _check_currency_matches_payout(self):
        for rec in self.filtered("transfer_id"):
            payout_currency = rec.transfer_id.crypto_currency_id
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

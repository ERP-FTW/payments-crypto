import hashlib
import json
import re
from decimal import Decimal, InvalidOperation

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


ATOMIC_RE = re.compile(r"^[0-9]+$")


def normalize_atomic(value):
    value = str(value or "").strip()
    if not ATOMIC_RE.fullmatch(value):
        raise ValidationError(_("Atomic quantities must contain digits only."))
    return value.lstrip("0") or "0"


def normalize_decimal(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError(_("Rate values must be exact decimal strings."))
    if not number.is_finite() or number <= 0:
        raise ValidationError(_("Rate values must be finite and strictly positive."))
    return format(number.normalize(), "f")


def canonical_json(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_digest(payload):
    canonical = payload if isinstance(payload, str) else canonical_json(payload)
    return hashlib.sha256(canonical.encode()).hexdigest()


class CryptoAsset(models.Model):
    _name = "crypto.asset"
    _description = "Crypto Asset"
    _order = "network_code, symbol"

    name = fields.Char(required=True)
    symbol = fields.Char(required=True, index=True)
    network_code = fields.Char(required=True, index=True)
    contract_address = fields.Char(index=True)
    is_native_asset = fields.Boolean(default=False)
    decimal_places = fields.Integer(required=True)
    res_currency_id = fields.Many2one("res.currency", ondelete="restrict")
    active = fields.Boolean(default=True)
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["symbol"] = (vals.get("symbol") or "").strip().upper()
            vals["network_code"] = (vals.get("network_code") or "").strip().lower()
            address = (vals.get("contract_address") or "").strip()
            # Only EVM hexadecimal addresses are case-insensitive.
            vals["contract_address"] = address.lower() if address.startswith("0x") else address or False
        return super().create(vals_list)

    def write(self, vals):
        if "symbol" in vals:
            vals["symbol"] = (vals["symbol"] or "").strip().upper()
        if "network_code" in vals:
            vals["network_code"] = (vals["network_code"] or "").strip().lower()
        return super().write(vals)

    @api.constrains("decimal_places", "is_native_asset", "contract_address")
    def _check_identity(self):
        for record in self:
            if not 0 <= record.decimal_places <= 36:
                raise ValidationError(_("Decimal places must be between 0 and 36."))
            if record.is_native_asset and record.contract_address:
                raise ValidationError(_("A native asset cannot have a contract address."))
            if not record.is_native_asset and not record.contract_address:
                raise ValidationError(_("A contract token must have a contract address."))
            domain = [("id", "!=", record.id), ("network_code", "=", record.network_code)]
            domain += [("symbol", "=", record.symbol), ("is_native_asset", "=", True)] if record.is_native_asset else [("contract_address", "=", record.contract_address)]
            if self.search_count(domain):
                raise ValidationError(_("This network-aware crypto asset identity already exists."))

    _sql_constraints = [
        ("token_network_contract_uniq", "unique(network_code, contract_address)", "This token contract already exists on the network."),
    ]


class ResCurrency(models.Model):
    _inherit = "res.currency"

    crypto_asset_id = fields.Many2one("crypto.asset", string="Authoritative Crypto Asset", ondelete="restrict")


class CryptoRateSnapshot(models.Model):
    _name = "crypto.rate.snapshot"
    _description = "Immutable Crypto Rate Snapshot"
    _order = "quoted_at desc, id desc"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    base_currency_id = fields.Many2one("res.currency", required=True, check_company=True)
    crypto_asset_id = fields.Many2one("crypto.asset", required=True, ondelete="restrict")
    purpose = fields.Selection([("checkout", "Checkout Quote"), ("settlement", "Settlement Measurement"), ("transfer", "Transfer Measurement"), ("disposal", "Disposal Measurement"), ("closing", "Period-End Measurement")], required=True)
    quoted_at = fields.Datetime(required=True)
    expires_at = fields.Datetime()
    source = fields.Char(required=True)
    source_pair = fields.Char(required=True)
    rate_crypto_per_base = fields.Char(required=True)
    rate_base_per_crypto = fields.Char(required=True)
    raw_payload = fields.Text(required=True)
    payload_hash = fields.Char(required=True, readonly=True, copy=False, index=True)
    state = fields.Selection([("active", "Active"), ("expired", "Expired"), ("consumed", "Consumed"), ("superseded", "Superseded")], required=True, default="active")
    supersedes_id = fields.Many2one("crypto.rate.snapshot", check_company=True, ondelete="restrict")
    consumed_at = fields.Datetime(readonly=True, copy=False)

    _frozen = {"company_id", "base_currency_id", "crypto_asset_id", "purpose", "quoted_at", "expires_at", "source", "source_pair", "rate_crypto_per_base", "rate_base_per_crypto", "raw_payload", "payload_hash"}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["rate_crypto_per_base"] = normalize_decimal(vals["rate_crypto_per_base"])
            vals["rate_base_per_crypto"] = normalize_decimal(vals["rate_base_per_crypto"])
            try:
                payload = json.loads(vals["raw_payload"])
                vals["raw_payload"] = canonical_json(payload)
            except (TypeError, json.JSONDecodeError):
                raise ValidationError(_("Raw payload must be valid JSON."))
            vals["payload_hash"] = payload_digest(vals["raw_payload"])
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda r: r.state in ("consumed", "superseded") and self._frozen.intersection(vals)):
            raise UserError(_("Consumed rate snapshots are immutable; create a superseding snapshot."))
        if vals.get("state") == "consumed":
            vals.setdefault("consumed_at", fields.Datetime.now())
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state in ("consumed", "superseded")):
            raise UserError(_("Consumed or superseded rate snapshots cannot be deleted."))
        return super().unlink()

    _sql_constraints = [("snapshot_payload_uniq", "unique(company_id, source, purpose, payload_hash)", "This rate payload was already recorded.")]


class CryptoProviderEvent(models.Model):
    _name = "crypto.provider.event"
    _description = "Immutable Crypto Provider Event"
    _order = "received_at desc, id desc"

    company_id = fields.Many2one("res.company", required=True, index=True)
    provider_id = fields.Many2one("crypto.cashout.provider", required=True, check_company=True, ondelete="restrict")
    event_type = fields.Char(required=True)
    provider_event_id = fields.Char(index=True)
    provider_object_id = fields.Char(index=True)
    payload_hash = fields.Char(required=True, readonly=True, index=True)
    raw_payload = fields.Text(required=True, readonly=True)
    signature = fields.Char(readonly=True, groups="payments_crypto_conversion.group_crypto_transfer_admin")
    signature_verified = fields.Boolean(readonly=True)
    received_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    processed_at = fields.Datetime(readonly=True)
    processing_state = fields.Selection([("received", "Received"), ("verified", "Verified"), ("processed", "Processed"), ("duplicate", "Duplicate"), ("rejected", "Rejected"), ("error", "Error")], required=True, default="received", readonly=True)
    error_message = fields.Text(readonly=True)
    settlement_id = fields.Many2one("crypto.settlement", readonly=True, check_company=True)
    transfer_id = fields.Many2one("crypto.cashout.payout", readonly=True, check_company=True)
    payment_transaction_id = fields.Many2one("payment.transaction", readonly=True, check_company=True)

    def write(self, vals):
        allowed = {"processed_at", "processing_state", "error_message", "settlement_id", "transfer_id", "payment_transaction_id"}
        if not self.env.su or set(vals) - allowed:
            raise AccessError(_("Provider events are append-only."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Provider events cannot be deleted."))

    _sql_constraints = [
        ("event_provider_event_uniq", "unique(provider_id, provider_event_id)", "This provider event ID already exists."),
        ("event_provider_payload_uniq", "unique(provider_id, payload_hash)", "This provider payload already exists."),
    ]


class CryptoSettlement(models.Model):
    _name = "crypto.settlement"
    _description = "Crypto Settlement"
    _order = "confirmed_at desc, id desc"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    direction = fields.Selection([("inbound", "Inbound"), ("outbound", "Outbound")], required=True)
    settlement_kind = fields.Selection([("customer_payment", "Customer Payment"), ("crypto_transfer", "Crypto Transfer"), ("network_fee", "Network Fee"), ("refund", "Refund"), ("adjustment", "Adjustment")], required=True)
    custody_kind = fields.Selection([("merchant", "Merchant Controlled"), ("provider", "Provider Custodied"), ("automatic_fiat", "Automatic Fiat Settlement"), ("clearing", "Clearing Only")], default="merchant", required=True)
    state = fields.Selection([("pending", "Pending"), ("confirmed", "Confirmed"), ("accounted", "Accounted"), ("reversed", "Reversed"), ("exception", "Exception")], required=True, default="pending")
    provider_id = fields.Many2one("crypto.cashout.provider", required=True, check_company=True, ondelete="restrict")
    crypto_asset_id = fields.Many2one("crypto.asset", required=True, ondelete="restrict")
    source_transaction_id = fields.Many2one("payment.transaction", check_company=True, ondelete="restrict")
    source_pos_payment_id = fields.Many2one("pos.payment", check_company=True, ondelete="restrict")
    source_transfer_id = fields.Many2one("crypto.cashout.payout", check_company=True, ondelete="restrict")
    provider_event_id = fields.Many2one("crypto.provider.event", required=True, check_company=True, ondelete="restrict")
    provider_payment_id = fields.Char(index=True)
    provider_transfer_id = fields.Char(index=True)
    provider_batch_id = fields.Char(index=True)
    network_transaction_id = fields.Char(index=True)
    payment_hash = fields.Char(index=True)
    destination_address = fields.Char()
    source_address = fields.Char()
    atomic_amount = fields.Char(required=True)
    fee_atomic_amount = fields.Char(default="0", required=True)
    settled_at = fields.Datetime(required=True)
    confirmed_at = fields.Datetime()
    confirmation_count = fields.Integer(default=0)
    rate_snapshot_id = fields.Many2one("crypto.rate.snapshot", check_company=True, ondelete="restrict")
    account_payment_id = fields.Many2one("account.payment", check_company=True, copy=False, ondelete="restrict")
    account_move_id = fields.Many2one("account.move", check_company=True, copy=False, ondelete="restrict")
    currency_move_id = fields.Many2one("res.currency.move", check_company=True, copy=False, ondelete="restrict")
    reversal_of_id = fields.Many2one("crypto.settlement", check_company=True, ondelete="restrict")
    notes = fields.Text()

    _economic = {"company_id", "direction", "settlement_kind", "custody_kind", "provider_id", "crypto_asset_id", "source_transaction_id", "source_pos_payment_id", "source_transfer_id", "provider_event_id", "provider_payment_id", "provider_transfer_id", "provider_batch_id", "network_transaction_id", "payment_hash", "destination_address", "source_address", "atomic_amount", "fee_atomic_amount", "settled_at", "confirmed_at", "rate_snapshot_id"}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["atomic_amount"] = normalize_atomic(vals["atomic_amount"])
            vals["fee_atomic_amount"] = normalize_atomic(vals.get("fee_atomic_amount", "0"))
            if vals.get("state") in ("confirmed", "accounted"):
                event = self.env["crypto.provider.event"].browse(vals.get("provider_event_id"))
                if not event.signature_verified:
                    raise ValidationError(_("A provider-driven settlement requires a verified event."))
                vals.setdefault("confirmed_at", vals.get("settled_at"))
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda r: r.state in ("confirmed", "accounted", "reversed") and self._economic.intersection(vals)):
            raise UserError(_("Confirmed settlements are immutable; create a reversal."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state != "pending" or r.account_move_id or r.account_payment_id):
            raise UserError(_("Confirmed or accounted settlements cannot be deleted."))
        return super().unlink()

    _sql_constraints = [
        ("settlement_provider_payment_uniq", "unique(provider_id, provider_payment_id)", "This provider payment is already settled."),
        ("settlement_provider_transfer_uniq", "unique(provider_id, provider_transfer_id)", "This provider transfer is already settled."),
        ("settlement_account_payment_uniq", "unique(account_payment_id)", "This payment already belongs to a settlement."),
        ("settlement_account_move_uniq", "unique(account_move_id)", "This journal entry already belongs to a settlement."),
        ("settlement_currency_move_uniq", "unique(currency_move_id)", "This currency move already belongs to a settlement."),
    ]

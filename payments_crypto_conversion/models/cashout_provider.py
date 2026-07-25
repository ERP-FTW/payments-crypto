import logging
import os
import uuid
import hmac
import hashlib
import json

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CryptoCashoutProvider(models.Model):
    _name = "crypto.cashout.provider"
    _description = "Crypto Transfer Provider"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Selection(
        selection=[("manual", "Manual"), ("mock_crypto", "Mock Crypto Provider")],
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
    environment = fields.Selection([("mock", "Mock"), ("test", "Test"), ("live", "Live")], required=True, default="mock")
    provider_uuid = fields.Char(required=True, readonly=True, copy=False, index=True, default=lambda self: str(uuid.uuid4()))
    ipn_secret = fields.Char(copy=False, groups="payments_crypto_conversion.group_crypto_transfer_admin")
    credential_source = fields.Selection([("database", "Database"), ("environment", "Environment Variable")], required=True, default="database")
    api_key_env_var = fields.Char(groups="payments_crypto_conversion.group_crypto_transfer_admin")
    password_env_var = fields.Char(groups="payments_crypto_conversion.group_crypto_transfer_admin")
    ipn_secret_env_var = fields.Char(groups="payments_crypto_conversion.group_crypto_transfer_admin")
    mock_scenario = fields.Selection([("immediate_success", "Immediate Success"), ("delayed_success", "Delayed Success"), ("failure", "Failure"), ("partial_success", "Partial Success"), ("submission_timeout", "Submission Timeout")], default="delayed_success", groups="payments_crypto_conversion.group_crypto_transfer_admin")
    mock_delay_seconds = fields.Integer(default=0, groups="payments_crypto_conversion.group_crypto_transfer_admin")
    mock_fixed_rate = fields.Char(default="50000.00", groups="payments_crypto_conversion.group_crypto_transfer_admin")
    mock_ipn_secret = fields.Char(copy=False, groups="payments_crypto_conversion.group_crypto_transfer_admin")
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _sql_constraints = [
        ("provider_uuid_uniq", "unique(provider_uuid)", "Provider callback UUIDs must be unique."),
        ("provider_company_code_uniq", "unique(company_id, code)", "A provider code may only be configured once per company."),
    ]

    def _credential(self, database_field, environment_field):
        self.ensure_one()
        if self.credential_source == "environment":
            variable = self[environment_field]
            if not variable:
                raise UserError(_("The credential environment variable name is required."))
            value = os.environ.get(variable)
            if not value:
                raise UserError(_("The configured credential environment variable is not available."))
            return value
        return self[database_field]

    def _get_ipn_secret(self):
        self.ensure_one()
        if self.environment == "mock":
            return self.mock_ipn_secret or self.ipn_secret
        return self._credential("ipn_secret", "ipn_secret_env_var")

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
        if self.code == "mock_crypto" and self.environment == "mock":
            return self.provider_create_mock_payout(payout)
        _logger.warning(
            "Provider %s does not implement payout creation for payout %s",
            self.display_name,
            payout.display_name,
        )
        raise UserError(
            _("Provider '%s' does not implement payout creation.")
            % self.display_name
        )

    def _canonical_ipn(self, payload):
        from .crypto_ledger import canonical_json
        return canonical_json(payload)

    def _sign_ipn(self, payload):
        secret = self._get_ipn_secret()
        if not secret:
            raise UserError(_("An IPN secret is required."))
        return hmac.new(secret.encode(), self._canonical_ipn(payload).encode(), hashlib.sha512).hexdigest()

    def process_signed_ipn(self, payload, signature):
        """Verify, append, and normalize one callback. Returns (event, duplicate)."""
        self.ensure_one()
        from .crypto_ledger import canonical_json, payload_digest, normalize_atomic
        canonical = canonical_json(payload)
        digest = payload_digest(canonical)
        existing = self.env["crypto.provider.event"].sudo().search([("provider_id", "=", self.id), ("payload_hash", "=", digest)], limit=1)
        if existing:
            return existing, True
        expected = self._sign_ipn(payload)
        verified = bool(signature) and hmac.compare_digest(expected.lower(), str(signature).lower())
        event_vals = {
            "company_id": self.company_id.id,
            "provider_id": self.id,
            "event_type": str(payload.get("event_type") or payload.get("payment_status") or payload.get("status") or "provider_ipn"),
            "provider_event_id": str(payload.get("event_id")) if payload.get("event_id") else False,
            "provider_object_id": str(payload.get("payment_id") or payload.get("payout_id") or payload.get("id") or ""),
            "payload_hash": digest,
            "raw_payload": canonical,
            "signature": signature,
            "signature_verified": verified,
            "processing_state": "verified" if verified else "rejected",
            "error_message": False if verified else _("Signature verification failed."),
        }
        event = self.env["crypto.provider.event"].sudo().create(event_vals)
        if not verified:
            return event, False
        transfer = self.env["crypto.cashout.payout"].sudo().search([
            ("cashout_provider_id", "=", self.id),
            "|", ("provider_batch_id", "=", event.provider_object_id), ("provider_payout_id", "=", event.provider_object_id),
        ], limit=1)
        status = str(payload.get("status") or payload.get("payment_status") or "").lower()
        successful = status == "finished"
        failed = status in {"failed", "rejected", "error", "expired"}
        settlement = self.env["crypto.settlement"]
        if transfer:
            event.sudo().write({"transfer_id": transfer.id})
            items = payload.get("withdrawals") or [payload]
            confirmed = 0
            for item in items:
                item_status = str(item.get("status") or status).lower()
                provider_transfer = str(item.get("id") or item.get("transfer_id") or "")
                line = transfer.withdrawal_ids.filtered(lambda l: l.provider_transfer_id == provider_transfer or l.external_idempotency_key == item.get("unique_external_id"))[:1]
                if not line and len(transfer.withdrawal_ids) == 1:
                    line = transfer.withdrawal_ids
                if item_status != "finished" or not line:
                    continue
                atomic = normalize_atomic(item.get("atomic_amount") or line.atomic_amount)
                executed_at = item.get("finished_at") or item.get("updated_at") or fields.Datetime.now()
                line.sudo().write({"status": item_status, "provider_transfer_id": provider_transfer or line.provider_transfer_id, "executed_atomic_amount": atomic, "executed_at": executed_at, "verified_event_id": event.id})
                settlement = self.env["crypto.settlement"].sudo().search([("provider_id", "=", self.id), ("provider_transfer_id", "=", provider_transfer)], limit=1)
                if not settlement:
                    settlement = self.env["crypto.settlement"].sudo().create({
                        "company_id": transfer.company_id.id, "direction": "outbound", "settlement_kind": "crypto_transfer", "provider_id": self.id,
                        "crypto_asset_id": transfer.config_id.crypto_asset_id.id, "source_transfer_id": transfer.id, "provider_event_id": event.id,
                        "provider_transfer_id": provider_transfer or False, "provider_batch_id": transfer.provider_batch_id, "network_transaction_id": item.get("hash"),
                        "destination_address": line.address, "atomic_amount": atomic, "settled_at": executed_at, "confirmed_at": executed_at, "state": "confirmed",
                    })
                confirmed += 1
            if successful:
                transfer.sudo().write({"state": "executed" if confirmed == len(transfer.withdrawal_ids) else "partially_executed"})
            elif failed:
                transfer.sudo().write({"state": "failed"})
            else:
                transfer.sudo().write({"state": "processing"})
        event.sudo().write({"settlement_id": settlement.id if settlement else False, "processing_state": "processed", "processed_at": fields.Datetime.now()})
        return event, False

    def _mock_payload(self, payout, status):
        self.ensure_one()
        return {"event_id": f"MOCK-EVENT-{payout.external_idempotency_key}-{status}", "payout_id": payout.provider_batch_id, "status": status,
                "withdrawals": [{"id": line.provider_transfer_id, "unique_external_id": line.external_idempotency_key, "status": status, "atomic_amount": line.atomic_amount, "finished_at": fields.Datetime.to_string(fields.Datetime.now())} for line in payout.withdrawal_ids]}

    def provider_create_mock_payout(self, payout):
        self.ensure_one()
        if self.environment != "mock" or self.code != "mock_crypto":
            raise UserError(_("Mock controls cannot be used with a test or live provider."))
        batch = f"MOCK-BATCH-{payout.external_idempotency_key}"
        payout.write({"provider_batch_id": batch, "provider_payout_id": batch, "state": "submitted"})
        for line in payout.withdrawal_ids:
            line.write({"provider_transfer_id": f"MOCK-TRANSFER-{line.external_idempotency_key}"})
        if self.mock_scenario == "submission_timeout":
            raise TimeoutError("Mock response intentionally lost")
        status = "finished" if self.mock_scenario == "immediate_success" else "processing"
        payload = self._mock_payload(payout, status)
        self.process_signed_ipn(payload, self._sign_ipn(payload))
        return True

    def action_advance_mock_transfer(self, payout):
        self.ensure_one()
        status = "failed" if self.mock_scenario == "failure" else "finished"
        payload = self._mock_payload(payout, status)
        return self.process_signed_ipn(payload, self._sign_ipn(payload))[0]

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
                "title": _("Crypto Transfer Provider"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

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
        help="Provider exchange rate captured at payment time.",
    )
    provider_invoice_id = fields.Char(string="Provider Invoice ID", copy=False)
    provider_payout_id = fields.Char(string="Provider Payout ID", copy=False)
    provider_payment_id = fields.Char(string="Provider Payment ID", copy=False)
    crypto_payment_link = fields.Char(string="Crypto Payment Link", copy=False)

    account_payment_id = fields.Many2one(
        "account.payment",
        string="Account Payment",
        readonly=True,
        copy=False,
        index=True,
    )
    account_payment_state = fields.Selection(
        related="account_payment_id.state",
        string="Account Payment State",
        store=True,
        readonly=True,
    )

    # Backward compatibility fields (standardize on the canonical fields above).
    crypto_invoice_id = fields.Char(
        string="Crypto Invoice ID",
        related="provider_invoice_id",
        readonly=False,
    )
    crypto_payment = fields.Boolean(string="Crypto Payment")
    crypto_payment_type = fields.Char(string="Crypto Payment Type")
    crypto_conversion_rate = fields.Float(
        string="Crypto Conversion Rate",
        related="crypto_rate",
        readonly=False,
    )
    crypto_invoiced_crypto_amount = fields.Monetary(
        string="Invoiced Crypto Amount",
        digits=(24, 12),
        related="crypto_amount",
        readonly=False,
    )

    def _crypto_is_relevant(self):
        self.ensure_one()
        return bool(
            self.provider_id.is_crypto_provider
            or self.crypto_currency_id
            or self.crypto_amount
            or self.provider_invoice_id
            or self.provider_payment_id
            or self.provider_payout_id
        )

    def _crypto_requires_account_payment(self):
        self.ensure_one()
        if self.state != "done" or not self._crypto_is_relevant():
            return False
        return not (
            self.account_payment_id and self.account_payment_id.state == "posted"
        )

    def _crypto_get_notification_date(self, notification_data=None):
        notification_data = notification_data or {}
        for key in (
            "settlement_date",
            "payment_date",
            "date",
            "updated_at",
            "created_at",
        ):
            value = notification_data.get(key)
            if not value:
                continue
            parsed_date = fields.Date.to_date(value)
            if parsed_date:
                return parsed_date
        return fields.Date.context_today(self)

    def _crypto_get_inbound_payment_method_line(self, journal):
        self.ensure_one()
        payment_method_lines = journal.inbound_payment_method_line_ids
        if not payment_method_lines:
            raise ValidationError(
                _(
                    "Crypto provider journal '%s' has no inbound payment method lines."
                )
                % journal.display_name
            )
        provider_code = self.provider_code or self.provider_id.code
        matching_line = payment_method_lines.filtered(
            lambda line: line.payment_method_id.code == provider_code
        )
        return (matching_line or payment_method_lines)[:1]

    def _crypto_validate_required_fields(self):
        self.ensure_one()
        missing = []
        if not self.crypto_currency_id:
            missing.append(_("crypto currency"))
        if not self.crypto_amount:
            missing.append(_("crypto amount"))
        if missing:
            raise ValidationError(
                _(
                    "Crypto transactions must define %s before accounting can be created."
                )
                % ", ".join(missing)
            )

    def _crypto_prepare_account_payment_vals(self, notification_data=None):
        self.ensure_one()
        self._crypto_validate_required_fields()

        provider = self.provider_id.with_company(self.company_id)
        journal = provider.journal_id
        if not journal:
            raise UserError(
                _(
                    "Crypto provider '%s' must define a journal before payments can be posted."
                )
                % provider.display_name
            )

        payment_method_line = self._crypto_get_inbound_payment_method_line(journal)
        payment_date = self._crypto_get_notification_date(notification_data)
        reference_bits = [self.reference]
        for provider_ref in (
            self.provider_invoice_id,
            self.provider_payment_id,
            self.provider_payout_id,
        ):
            if provider_ref:
                reference_bits.append(provider_ref)

        return {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_id.id,
            "currency_id": self.crypto_currency_id.id,
            "amount": self.crypto_amount,
            "journal_id": journal.id,
            "date": payment_date,
            "ref": " - ".join(reference_bits),
            "payment_reference": self.reference,
            "payment_transaction_id": self.id,
            "company_id": self.company_id.id,
            "payment_method_line_id": payment_method_line.id,
        }

    def _crypto_get_or_create_account_payment(self, notification_data=None):
        self.ensure_one()
        if self.account_payment_id:
            return self.account_payment_id

        payment = (
            self.env["account.payment"]
            .with_company(self.company_id)
            .search([("payment_transaction_id", "=", self.id)], limit=1)
        )
        if payment:
            self.account_payment_id = payment
            return payment

        payment_vals = self._crypto_prepare_account_payment_vals(
            notification_data=notification_data
        )
        payment = self.env["account.payment"].with_company(self.company_id).create(
            payment_vals
        )
        self.account_payment_id = payment
        return payment

    def _crypto_sync_payment_metadata(self, payment):
        self.ensure_one()
        metadata_vals = {
            "payment_transaction_id": self.id,
            "provider_invoice_id": self.provider_invoice_id,
            "provider_payment_id": self.provider_payment_id,
            "provider_payout_id": self.provider_payout_id,
            "crypto_currency_id": self.crypto_currency_id.id,
            "crypto_amount": self.crypto_amount,
            "crypto_rate": self.crypto_rate,
            "crypto_payment_link": self.crypto_payment_link,
        }
        payment.with_company(self.company_id).write(metadata_vals)

    def _crypto_post_account_payment(self):
        self.ensure_one()
        payment = self.account_payment_id
        if not payment:
            return False
        if payment.state != "posted":
            payment.with_company(self.company_id).action_post()
        return payment

    def _crypto_sync_accounting(self, notification_data=None):
        for tx in self:
            if not tx._crypto_requires_account_payment():
                continue
            payment = tx._crypto_get_or_create_account_payment(
                notification_data=notification_data
            )
            tx._crypto_sync_payment_metadata(payment)
            tx._crypto_post_account_payment()
            _logger.info(
                "Synced crypto accounting for transaction %s with payment %s",
                tx.reference,
                payment.display_name,
            )
        return True

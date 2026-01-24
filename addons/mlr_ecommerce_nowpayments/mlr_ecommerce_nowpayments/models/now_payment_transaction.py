# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    @staticmethod
    def _now_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _get_specific_rendering_values(self, processing_values):
        """Override to provide NowPayments-specific checkout info."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "now":
            return res

        return {
            "reference": self.reference,
            "amount": self.amount,
            "currency_id": self.currency_id.name,
            "api_url": "/payment/now/createInvoice",
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find transaction based on NowPayments notification."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "now" or len(tx) == 1:
            return tx

        reference = notification_data.get("order_id")
        tx = self.search(
            [("reference", "=", reference), ("provider_code", "=", "now")],
            limit=1,
        )
        if not tx:
            raise ValidationError(
                _("NowPayments: No transaction found matching reference %s.")
                % reference
            )
        return tx

    def _now_get_crypto_currency(self, currency_code):
        currency_code = (currency_code or "").upper()
        if not currency_code:
            return self.env["res.currency"]
        return self.env["res.currency"].with_company(self.company_id).search(
            [("name", "=", currency_code)], limit=1
        )

    def _now_sync_normalized_fields(self, notification_data):
        self.ensure_one()
        currency_code = (
            notification_data.get("crypto_currency")
            or notification_data.get("pay_currency")
        )
        crypto_currency = self._now_get_crypto_currency(currency_code)
        crypto_amount = self._now_float(notification_data.get("crypto_amount"))
        price_amount = self._now_float(notification_data.get("price_amount"))
        crypto_rate = self._now_float(notification_data.get("crypto_rate"))
        if not crypto_rate and crypto_amount and price_amount:
            crypto_rate = price_amount / crypto_amount

        write_vals = {
            "provider_invoice_id": notification_data.get("provider_invoice_id")
            or self.provider_invoice_id,
            "provider_payment_id": notification_data.get("provider_payment_id")
            or self.provider_payment_id,
            "provider_payout_id": notification_data.get("provider_payout_id")
            or self.provider_payout_id,
            "crypto_payment_link": notification_data.get("crypto_payment_link")
            or self.crypto_payment_link,
        }
        if crypto_currency:
            write_vals["crypto_currency_id"] = crypto_currency.id
        if crypto_amount:
            write_vals["crypto_amount"] = crypto_amount
        if crypto_rate:
            write_vals["crypto_rate"] = crypto_rate

        self.with_company(self.company_id).write(write_vals)
        if write_vals.get("provider_payment_id"):
            self.with_company(self.company_id).write(
                {"provider_reference": write_vals["provider_payment_id"]}
            )

        if currency_code and not crypto_currency:
            _logger.warning(
                "NowPayments currency %s is not configured in Odoo.", currency_code
            )

    def _process_notification_data(self, notification_data):
        """Process NowPayments notification and update transaction state."""
        self.ensure_one()
        _logger.info("Processing NowPayments notification: %s", notification_data)

        super()._process_notification_data(notification_data)
        if self.provider_code != "now":
            return

        self._now_sync_normalized_fields(notification_data)

        payment_status = notification_data.get("payment_status")
        if not payment_status:
            raise ValidationError(_("NowPayments: Missing payment status."))

        if payment_status in ("waiting", "confirming"):
            self._set_pending()
        elif payment_status in ("finished", "confirmed", "sending"):
            self._set_done()
            if self.account_payment_id and self.account_payment_id.state == "posted":
                return
            try:
                self._crypto_sync_accounting(notification_data)
            except (UserError, ValidationError) as err:
                _logger.exception("NowPayments accounting sync failed: %s", err)
                self._set_error(str(err))
        elif payment_status in ("failed", "expired", "refunded"):
            self._set_canceled()
        else:
            _logger.warning(
                "Unknown payment status from NowPayments: %s", payment_status
            )
            self._set_error(_("Unknown payment status: %s") % payment_status)

# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    crypto_invoice_id = fields.Char('NowPayments Invoice ID')

    def _get_specific_rendering_values(self, processing_values):
        """Override to provide NowPayments-specific checkout info."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'now':
            return res

        return {
            'reference': self.reference,
            'amount': self.amount,
            'currency_code': self.currency_id.name,
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find transaction based on NowPayments notification."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'now' or len(tx) == 1:
            return tx

        reference = notification_data.get('order_id')
        tx = self.search([
            ('reference', '=', reference),
            ('provider_code', '=', 'now')
        ], limit=1)
        if not tx:
            raise ValidationError(
                "NowPayments: No transaction found matching reference %s." % reference
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Process NowPayments notification and update transaction state."""
        self.ensure_one()
        _logger.info(f"Processing NowPayments notification: {notification_data}")

        super()._process_notification_data(notification_data)
        
        if self.provider_code != 'now':
            return
        journal = self.provider_id.journal_id
        payment_method_line = journal.inbound_payment_method_line_ids[:1] if journal else None
        if payment_method_line:
            self.payment_method_line_id = payment_method_line.id
            _logger.info(f"Processing NowPayments payment_method_line: {payment_method_line.id}")
        else:
            _logger.warning("No inbound payment method line found for NowPayments journal.")
        self.provider_reference = notification_data.get('payment_id')

        payment_method = self.env['payment.method']._get_from_code('nowpayments')
        self.payment_method_id = payment_method or self.payment_method_id

        payment_status = notification_data.get('payment_status')
        if not payment_status:
            raise ValidationError("NowPayments: Missing payment status.")

        if payment_status in ('waiting', 'confirming'):
            self._set_pending()
        elif payment_status in ('finished', 'confirmed', 'sending'):
            self._set_done()
        elif payment_status in ('failed', 'expired', 'refunded'):
            self._set_canceled()
        else:
            _logger.warning(f"Unknown payment status from NowPayments: {payment_status}")
            self._set_error(f"Unknown payment status: {payment_status}")

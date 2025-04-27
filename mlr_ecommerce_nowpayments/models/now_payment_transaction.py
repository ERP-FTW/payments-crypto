# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from odoo import api, models, fields
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    #now_invoice_id = fields.Char('now Invoice ID')
    #now_conversion_rate = fields.Float('Conversion rate')
    #now_invoiced_sat_amount = fields.Float('Invoiced Satoshi Amount', digits=(12, 8))
    #now_payment_link = fields.Char('now Payment Link')
    #now_payment_link_qr_code = fields.Binary('QR Code', compute="_generate_qr")


    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Nowpayments-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'now':
            return res

        base_url = self.provider_id.get_base_url()
        return {
            'reference': self.reference,
            'amount': self.amount,
            'currency_code': self.currency_id.name,
        }



    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on NowPayments data.
    
        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'now' or len(tx) == 1:
            return tx
    
        reference = notification_data.get('order_id')
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'now')])
        if not tx:
            raise ValidationError("NowPayments: " + _("No transaction found matching reference %s.", reference))
            return tx
    
    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on NowPayments data.
    
        Note: self.ensure_one()
    
        :param dict notification_data: The notification data sent by the provider
        :return: None
        """
        _logger.info(f"Called now _process_notification_data. Passed args are {notification_data}")
        super()._process_notification_data(notification_data)
        if self.provider_code != 'now':
            return
    
        # Update the provider reference.
        self.provider_reference = notification_data.get('payment_id')
    
        # Update the payment method.
        payment_method = self.env['payment.method']._get_from_code('nowpayments')
        self.payment_method_id = payment_method or self.payment_method_id
    
        # Update the payment state.
        payment_status = notification_data.get('payment_status')
        if not payment_status:
            raise ValidationError("NowPayments: " + _("Received data with missing payment status."))
        if payment_status in ('waiting', 'confirming'):
            self._set_pending()
        elif payment_status in ('finished', 'confirmed', 'sending'):
            self._set_done()
        elif payment_status in ('failed', 'expired', 'refunded'):
            self._set_canceled()
        else:
            _logger.warning(
                "NowPayments: Received unknown payment status '%s' for transaction reference %s",
                payment_status, self.reference
            )
            self._set_error(
                "NowPayments: " + _("Unknown payment status: %s", payment_status)
            )



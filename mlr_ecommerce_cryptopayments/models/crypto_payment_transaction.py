# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from odoo import api, models, fields
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    crypto_invoice_id = fields.Char('Crypto Invoice ID')
    crypto_payment = fields.Boolean('Crypto Payment')
    crypto_payment_type = fields.Char('Crypto Payment Type')
    crypto_conversion_rate = fields.Float('Crypto Conversion rate')
    crypto_invoiced_crypto_amount = fields.Float('Invoiced Crypto Amount', digits=(12, 8))
    crypto_payment_link = fields.Char('Crypto Payment Link')
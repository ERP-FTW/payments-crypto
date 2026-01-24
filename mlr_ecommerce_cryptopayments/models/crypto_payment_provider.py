
import logging
import uuid

import requests
from werkzeug.urls import url_encode, url_join, url_parse

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    is_crypto_provider = fields.Boolean('Crypto Payment Provider')
    crypto_server_url = fields.Char(string='Server URL')
    crypto_api_key = fields.Char(string='API Key')
    crypto_min_amount = fields.Float(string='Provider minimum Fiat Amount')
    crypto_max_amount = fields.Float(string='Provider maximum Fiat Amount')



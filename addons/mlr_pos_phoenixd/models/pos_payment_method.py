# coding: utf-8
import logging
from datetime import datetime

import requests
from types import SimpleNamespace

from odoo import api, fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)
TIMEOUT = 10
SATS_PER_BTC = 100000000


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [('phoenixd', 'Phoenixd')]

    def _default_phoenixd_fiat_currency(self):
        return self.env.company.currency_id or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)

    def _default_phoenixd_crypto_currency(self):
        return self.env['res.currency'].search([('name', '=', 'BTC')], limit=1)

    phoenixd_base_url = fields.Char(string='Phoenixd Base URL', default='http://localhost:9740')
    phoenixd_http_password = fields.Char(string='Phoenixd HTTP Password')
    phoenixd_payment_type = fields.Selection(
        [('lightning', 'BTC-Lightning')],
        string='Phoenixd Payment Type',
        default='lightning',
    )
    phoenixd_fiat_currency_id = fields.Many2one(
        'res.currency',
        string='Phoenixd Fiat Currency',
        default=_default_phoenixd_fiat_currency,
    )
    phoenixd_crypto_currency_id = fields.Many2one(
        'res.currency',
        string='Phoenixd Crypto Currency',
        default=_default_phoenixd_crypto_currency,
    )
    phoenixd_usd_per_btc_rate = fields.Float(string='Manual USD/BTC Rate')

    def _get_phoenixd_settings(self):
        self.ensure_one()
        base_url = (self.phoenixd_base_url or '').strip().rstrip('/')
        password = (self.phoenixd_http_password or '').strip()

        if not base_url:
            raise UserError(_('Please set the Phoenixd base URL on this payment method.'))
        if not password:
            raise UserError(_('Please set the Phoenixd HTTP password on this payment method.'))

        return {
            'base_url': base_url,
            'password': password,
        }

    def _phoenixd_request(self, method, path, data=None):
        settings = self._get_phoenixd_settings()
        url = '%s/%s' % (settings['base_url'], path.lstrip('/'))
        try:
            response = requests.request(
                method=method,
                url=url,
                data=data,
                auth=('', settings['password']),
                timeout=TIMEOUT,
            )
        except requests.exceptions.RequestException as error:
            raise UserError(_('Phoenixd network failure while calling %(path)s: %(error)s') % {
                'path': path,
                'error': error,
            })

        try:
            response_json = response.json()
        except ValueError:
            raise UserError(_('Phoenixd returned a non-JSON response for %(path)s.') % {'path': path})

        if not response.ok:
            raise UserError(_('Phoenixd request to %(path)s failed with HTTP %(status)s: %(body)s') % {
                'path': path,
                'status': response.status_code,
                'body': response.text[:500],
            })

        return response_json

    def _test_connection(self):
        if self.use_payment_terminal != 'phoenixd':
            return super()._test_connection()
        self._phoenixd_request('GET', '/getbalance')
        return SimpleNamespace(status_code=200)

    def action_phoenixd_get_balance(self):
        self.ensure_one()
        balance = self._phoenixd_request('GET', '/getbalance')
        _logger.info('Phoenixd balance check succeeded for payment method %s', self.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phoenixd Balance'),
                'message': _('Phoenixd balance response: %s') % balance,
                'type': 'success',
                'sticky': False,
            },
        }

    def _phoenixd_get_rate(self):
        self.ensure_one()
        rate = self.phoenixd_usd_per_btc_rate
        if not rate:
            raise UserError(_('Please set a manual USD/BTC conversion rate on this payment method.'))
        return rate

    @staticmethod
    def _phoenixd_timestamp_to_string(timestamp_ms):
        if not timestamp_ms:
            return False
        return fields.Datetime.to_string(datetime.utcfromtimestamp(timestamp_ms / 1000))

    @api.model
    def phoenixd_create_crypto_invoice(self, args):
        try:
            cryptopay_pm = self.env['pos.payment.method'].browse(args['pm_id'])
            if cryptopay_pm.use_payment_terminal != 'phoenixd':
                return {'code': _('Payment method is not configured for Phoenixd.')}

            rate = cryptopay_pm._phoenixd_get_rate()
            fiat_amount = float(args.get('amount') or 0.0)
            amount_sat = int(round((fiat_amount / rate) * SATS_PER_BTC))
            if amount_sat <= 0:
                return {'code': _('Phoenixd invoice amount must be at least 1 sat.')}

            order_id = args.get('order_id') or ''
            payload = {
                'description': 'Odoo POS %s' % order_id,
                'amountSat': amount_sat,
            }
            response_json = cryptopay_pm._phoenixd_request('POST', '/createinvoice', payload)
            serialized = response_json.get('serialized') or response_json.get('invoice') or ''
            payment_hash = response_json.get('paymentHash') or response_json.get('payment_hash') or response_json.get('hash')
            crypto_amount = amount_sat / SATS_PER_BTC
            result = {
                'code': 0,
                'invoice_id': payment_hash,
                'invoice': serialized,
                'cryptopay_payment_link': 'lightning:%s' % serialized,
                'cryptopay_payment_type': 'BTC-lightning',
                'crypto_amt': amount_sat,
                'crypto_amount_currency': crypto_amount,
                'invoiced_crypto_amount': amount_sat,
                'requested_sat_amount': amount_sat,
                'conversion_rate': rate,
                'crypto_rate': rate,
                'crypto_unit': 'sat',
                'crypto_currency_code': (cryptopay_pm.phoenixd_crypto_currency_id.name or 'BTC'),
                'crypto_currency_id': cryptopay_pm.phoenixd_crypto_currency_id.id,
                'fiat_currency_code': (cryptopay_pm.phoenixd_fiat_currency_id.name or 'USD'),
                'fiat_currency_id': cryptopay_pm.phoenixd_fiat_currency_id.id,
                'provider_status': 'invoice_created',
                'provider_raw_json': response_json,
            }
            _logger.info('Created Phoenixd invoice %s for payment method %s', payment_hash, cryptopay_pm.id)
            return result
        except UserError as error:
            return {'code': str(error)}
        except Exception as error:
            _logger.exception('Phoenixd invoice creation failed')
            return {'code': str(error)}

    @api.model
    def phoenixd_check_payment_status(self, args):
        try:
            cryptopay_pm = self.env['pos.payment.method'].browse(args['pm_id'])
            if cryptopay_pm.use_payment_terminal != 'phoenixd':
                return {'code': _('Payment method is not configured for Phoenixd.')}

            invoice_id = args.get('invoice_id')
            if not invoice_id:
                return {'code': 404, 'status': 'pending'}

            response_json = cryptopay_pm._phoenixd_request('GET', '/payments/incoming/%s' % invoice_id)
            requested_sat = int(response_json.get('requestedSat') or response_json.get('amountSat') or 0)
            received_sat = int(response_json.get('receivedSat') or 0)
            completed_at = response_json.get('completedAt')
            expires_at = response_json.get('expiresAt')
            is_paid = bool(response_json.get('isPaid'))
            provider_completed_at = cryptopay_pm._phoenixd_timestamp_to_string(completed_at)

            if is_paid and received_sat >= requested_sat and completed_at:
                status = 'paid'
            elif expires_at and datetime.utcnow().timestamp() * 1000 >= expires_at:
                status = 'expired'
            else:
                status = 'pending'

            result = {
                'code': 0,
                'status': status,
                'payment_hash': response_json.get('paymentHash') or response_json.get('payment_hash') or invoice_id,
                'requested_sat_amount': requested_sat,
                'received_sat_amount': received_sat,
                'provider_fee_sat': int(response_json.get('fees') or 0),
                'provider_completed_at': provider_completed_at,
                'provider_status': status,
                'provider_raw_json': response_json,
            }
            _logger.info('Phoenixd invoice %s status: %s', invoice_id, status)
            return result
        except UserError as error:
            return {'code': str(error), 'status': 'error'}
        except Exception as error:
            _logger.exception('Phoenixd status check failed')
            return {'code': str(error), 'status': 'error'}

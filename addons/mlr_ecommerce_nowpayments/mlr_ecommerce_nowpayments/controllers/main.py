import hashlib
import hmac
import json
import logging
import math
import re

from werkzeug.exceptions import Forbidden

from odoo.exceptions import ValidationError
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


def _js_number(value):
    """Format a number the way JavaScript's JSON.stringify does."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if math.isnan(value) or math.isinf(value):
        return 'null'
    if value.is_integer() and abs(value) < 1e21:
        return str(int(value))
    text = repr(value)
    if 'e' in text:
        mantissa, exponent = text.split('e')
        sign = '-' if exponent.startswith('-') else '+'
        text = f"{mantissa}e{sign}{exponent.lstrip('+-').lstrip('0') or '0'}"
    return text


def nowpayments_signed_message(value):
    """Serialize a notification body as NOWPayments signs it.

    NOWPayments' reference implementation sorts object keys recursively and signs
    `JSON.stringify(sorted)`. Python's json module formats some numbers differently from
    JavaScript (`1.0` versus `1`), so the serialization is reproduced here explicitly instead of
    relying on json.dumps.
    """
    if isinstance(value, dict):
        items = ','.join(
            f"{json.dumps(str(key), ensure_ascii=False)}:{nowpayments_signed_message(value[key])}"
            for key in sorted(value, key=str)
        )
        return '{' + items + '}'
    if isinstance(value, list):
        # The reference sortObject() turns an array into an object keyed by index.
        return nowpayments_signed_message({str(i): item for i, item in enumerate(value)})
    if value is None:
        return 'null'
    if isinstance(value, (int, float)):
        return _js_number(value)
    return json.dumps(value, ensure_ascii=False)


def nowpayments_signature(secret, body):
    return hmac.new(
        secret.encode('utf-8'), nowpayments_signed_message(body).encode('utf-8'), hashlib.sha512,
    ).hexdigest()


class NowPaymentsController(Controller):
    _return_url = '/payment/now/return'
    _create_invoice_url = '/payment/now/createInvoice'
    _ipn_url = '/payment/now/ipn'

    @staticmethod
    def _get_now_tx(reference):
        if not reference:
            return request.env['payment.transaction']
        return request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference), ('provider_code', '=', 'now'),
        ], limit=1)

    @route(_create_invoice_url, type='http', auth='public', methods=['POST'], csrf=False)
    def create_invoice(self, **post):
        """Open (or reopen) the NOWPayments invoice of a checkout transaction.

        Only `reference` is read from the form. Amount, currency, provider and company all come
        from the transaction itself.
        """
        tx_sudo = self._get_now_tx(post.get('reference'))
        if not tx_sudo:
            _logger.warning("NOWPayments: invoice requested for unknown reference %s",
                            post.get('reference'))
            return request.redirect('/payment/status')
        try:
            invoice_url = tx_sudo._nowpayments_get_invoice_url()
        except ValidationError as error:
            _logger.warning("NOWPayments: no invoice for %s: %s", tx_sudo.reference, error)
            if tx_sudo.state == 'draft':
                tx_sudo._set_error(str(error))
            return request.redirect('/payment/status')
        return request.redirect(invoice_url, local=False)

    @route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def custom_process_transaction(self, **post):
        """The buyer came back from NOWPayments: settle from the provider's state if available."""
        tx_sudo = self._get_now_tx(post.get('ref') or post.get('reference'))
        if tx_sudo:
            try:
                tx_sudo._nowpayments_reconcile()
            except ValidationError as error:
                _logger.warning("NOWPayments: return for %s not settled yet: %s",
                                tx_sudo.reference, error)
        return request.redirect('/payment/status')

    @route(_ipn_url, type='http', auth='public', methods=['POST'], csrf=False)
    def nowpayments_ipn(self):
        """Instant payment notification.

        The signature is checked with the IPN secret of the transaction's own provider. The body
        is then used only to identify the payment; its state is re-read from NOWPayments.
        """
        raw = request.httprequest.get_data()
        try:
            data = json.loads(raw)
        except ValueError:
            _logger.warning("NOWPayments: notification with a non-JSON body refused")
            raise Forbidden()
        if not isinstance(data, dict):
            raise Forbidden()
        _logger.info("NOWPayments notification for order %s payment %s status %s",
                     data.get('order_id'), data.get('payment_id'), data.get('payment_status'))
        try:
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                'now', data)
        except ValidationError:
            _logger.warning("NOWPayments: notification for unknown order %s", data.get('order_id'))
            return request.make_json_response('')

        secret = tx_sudo.provider_id.sudo().nowpayments_ipn_secret
        received = request.httprequest.headers.get('x-nowpayments-sig') or ''
        if not secret or not re.fullmatch(r'[0-9a-fA-F]{128}', received) or not hmac.compare_digest(
            received.lower(), nowpayments_signature(secret, data)
        ):
            _logger.warning("NOWPayments: notification for %s refused (signature)", tx_sudo.reference)
            raise Forbidden()

        try:
            tx_sudo._handle_notification_data('now', {
                'order_id': tx_sudo.reference, 'payment_id': data.get('payment_id'),
            })
        except ValidationError as error:
            # Acknowledge: retrying the same notification cannot make it valid.
            _logger.warning("NOWPayments: notification for %s not applied: %s",
                            tx_sudo.reference, error)
        return request.make_json_response('')

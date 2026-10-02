import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Seconds before an outbound NOWPayments call is abandoned.
NOWPAYMENTS_TIMEOUT = 20


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('now', "now")], ondelete={'now': 'set default'})
    nowpayments_username = fields.Char(
        string="NowPayments Username",
        help="Dashboard e-mail. Only used to obtain the short-lived token that the payment listing "
             "endpoint requires (reconciliation of payments whose notification was missed).")
    nowpayments_password = fields.Char(string="NowPayments Password", groups='base.group_system')
    nowpayments_ipn_secret = fields.Char(
        string="NowPayments IPN Secret Key", groups='base.group_system',
        help="Secret from the NOWPayments store settings used to verify the x-nowpayments-sig "
             "header of payment notifications. Without it, notifications are refused and payments "
             "are completed only by the return page and the reconciliation job.")

    # === API helpers === #

    def _nowpayments_api_base(self):
        self.ensure_one()
        base = (self.crypto_server_url or '').strip().rstrip('/')
        if not base:
            raise ValidationError(_("NOWPayments: the provider has no server URL."))
        return base

    def _nowpayments_make_request(self, endpoint, payload=None, method='GET', jwt=False):
        """Call the NOWPayments API with this provider's own credentials.

        The provider is always the transaction's provider, so a database with one NOWPayments
        account per company uses the right account for each payment.

        Credentials never reach the log: only the method, the endpoint and the HTTP status are
        logged, never headers, and never the body of the authentication call.

        :return: The decoded JSON response.
        :raise ValidationError: On a transport error or a non-2xx answer.
        """
        self.ensure_one()
        url = f"{self._nowpayments_api_base()}{endpoint}"
        headers = {
            'x-api-key': self.crypto_api_key or '',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if jwt:
            headers['Authorization'] = f"Bearer {self._nowpayments_get_jwt()}"
        try:
            response = requests.request(
                method, url, json=payload if method != 'GET' else None, headers=headers,
                timeout=NOWPAYMENTS_TIMEOUT,
            )
        except requests.exceptions.RequestException as error:
            _logger.warning("NOWPayments %s %s failed: %s", method, endpoint, type(error).__name__)
            raise ValidationError(_("NOWPayments: could not reach the provider.")) from error
        _logger.info("NOWPayments %s %s -> HTTP %s", method, endpoint, response.status_code)
        try:
            content = response.json()
        except ValueError:
            content = {}
        if not 200 <= response.status_code < 300:
            message = content.get('message') if isinstance(content, dict) else None
            raise ValidationError(_(
                "NOWPayments: %(endpoint)s answered HTTP %(status)s%(detail)s",
                endpoint=endpoint, status=response.status_code,
                detail=f" ({message})" if message else '',
            ))
        return content

    def _nowpayments_get_jwt(self):
        """Return a bearer token for the endpoints that need one (the payment listing)."""
        self.ensure_one()
        provider_sudo = self.sudo()
        if not provider_sudo.nowpayments_username or not provider_sudo.nowpayments_password:
            raise ValidationError(_(
                "NOWPayments: listing payments needs the dashboard e-mail and password."))
        content = provider_sudo._nowpayments_make_request('/v1/auth', payload={
            'email': provider_sudo.nowpayments_username,
            'password': provider_sudo.nowpayments_password,
        }, method='POST')
        token = content.get('token') if isinstance(content, dict) else None
        if not token:
            raise ValidationError(_("NOWPayments: authentication returned no token."))
        return token

    # === Connection test === #

    def test_now_server_connection(self):
        """Check that the API key is accepted, through an endpoint that requires it."""
        self.ensure_one()
        try:
            self._nowpayments_make_request('/v1/currencies?fixed_rate=false')
        except ValidationError as error:
            _logger.info("NOWPayments connection test failed for provider %s: %s", self.id, error)
            return False
        return True

    def action_test_connection(self):
        is_success = self.test_now_server_connection()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection Testing"),
                "message": _("The API key is accepted.") if is_success else _(
                    "The server refused the API key or could not be reached."),
                "sticky": False,
                "type": "success" if is_success else "danger",
            },
        }

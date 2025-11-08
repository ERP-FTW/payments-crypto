# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import json
import requests

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)

class NowPaymentsController(Controller):
    _return_url = '/payment/now/return'
    _create_invoice_url = '/payment/now/createInvoice'

    def nowApiCall(self, payload, api, method, jwt=0):
        try:
            _logger.info(f"Called nowApiCall")

            crypto_details = request.env['payment.provider'].sudo().search([('code', '=', 'now')], limit=1)
            base_url = crypto_details.crypto_server_url.rstrip('/')  # <- normalize
            api_key = crypto_details.crypto_api_key

            server_url = f"{base_url}{api}"
            if jwt:
                jwt_payload = {
                    "email": crypto_details.nowpayments_username,
                    "password": crypto_details.nowpayments_password,
                }
                jwt_response = self.nowApiCall(jwt_payload, '/v1/auth', 'POST', jwt=0)
                jwtoken = jwt_response.json()['token']
                headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {jwtoken}",
                }
            else:
                headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }

            if method == "GET":
                response = requests.get(server_url, headers=headers, timeout=20)
            elif method == "POST":
                # ✅ send JSON correctly
                response = requests.post(server_url, json=payload, headers=headers, timeout=20)

            # ✅ robust logging: don't blow up on non-JSON
            try:
                body = response.json()
            except Exception:
                body = response.text[:500]  # log first 500 chars if not JSON

            _logger.info("NOWPayments %s %s -> %s %s", method, server_url, response.status_code, body)
            return response
        except Exception as e:
            _logger.exception(f"Error during NowPayments API call: {e}")
            raise

    @route(_create_invoice_url, type='http', auth='public', methods=['POST'], csrf=False)
    def create_invoice(self, **post):
        """Create a NowPayments invoice."""
        try:
            _logger.info(f"Called create_invoice with data: {post}")
            trn = request.env['payment.transaction'].sudo().search([
                ('reference', '=', post['reference']),
                ('provider_code', '=', 'now')
            ], limit=1)

            crypto_details = request.env['payment.provider'].sudo().search([('code', '=', 'now')], limit=1)
            crypto_min_amount = crypto_details.crypto_min_amount
            crypto_max_amount = crypto_details.crypto_max_amount

            amount = float(post['amount'])
            if amount < crypto_min_amount or amount > crypto_max_amount:
                _logger.warning(f"Amount {amount} outside allowed range.")
                return request.redirect('/shop/payment')

            web_base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            success_url = f"{web_base_url}/payment/now/return?ref={post['reference']}"

            payload = {
                "price_amount": amount,
                "price_currency": post['currency_id'],
                "success_url": success_url,
                "order_id": post['reference'],
            }
            api_response = self.nowApiCall(payload, '/v1/invoice', 'POST')
            api_response_json = api_response.json()

            if api_response.status_code == 200:
                payment_method = request.env['payment.method'].sudo()._get_from_code('nowpayments')
                trn.write({
                    'crypto_invoice_id': api_response_json.get('id'),
                    'payment_method_id': payment_method.id,
                })
                return request.redirect(api_response_json.get('invoice_url'), local=False)
            else:
                _logger.warning(f"Failed to create NowPayments invoice: {api_response.text}")
                trn._set_error("Failed to create NowPayments invoice.")
                return request.redirect('/payment/status')

        except Exception as e:
            _logger.exception(f"Error in create_invoice: {e}")
            return request.redirect('/payment/status')

    @route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    @route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def custom_process_transaction(self, **post):
        try:
            _logger.info(f"Handling NowPayments return with data: {post}")

            # ✅ accept both ?ref=... and ?reference=...
            ref = post.get('ref') or post.get('reference')

            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                'now', {'order_id': ref}  # ✅ pass the actual reference
            )

            api_response = self.nowApiCall({}, '/v1/payment/?limit=10&page=0&sortBy=created_at&orderBy=desc', 'GET',
                                           jwt=1)
            res_json = api_response.json().get('data', []) if api_response.ok else []

            for payment in res_json:
                if payment.get('order_id') == ref:
                    notification_data = {
                        'payment_status': payment.get('payment_status'),
                        'payment_id': payment.get('payment_id'),
                        'amount': payment.get('price_amount'),
                        'currency_id': payment.get('price_currency'),
                    }
                    tx_sudo._handle_notification_data('now', notification_data)
                    _logger.info(f"Processed NowPayments transaction for ref {ref}")
                    break

            return request.redirect('/payment/status')

        except Exception as e:
            _logger.exception(f"Error handling NowPayments transaction return: {e}")
            return request.redirect('/payment/status')


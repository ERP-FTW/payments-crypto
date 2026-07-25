# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

import requests

from odoo import fields
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


class NowPaymentsController(Controller):
    _return_url = "/payment/now/return"
    _create_invoice_url = "/payment/now/createInvoice"

    @staticmethod
    def _now_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def nowApiCall(self, payload, api, method, jwt=0):
        _logger.info("Called nowApiCall")

        crypto_details = request.env["payment.provider"].sudo().search(
            [("code", "=", "now")], limit=1
        )
        base_url = crypto_details.crypto_server_url.rstrip("/")
        api_key = crypto_details.crypto_api_key

        server_url = f"{base_url}{api}"
        if jwt:
            jwt_payload = {
                "email": crypto_details.nowpayments_username,
                "password": crypto_details.nowpayments_password,
            }
            jwt_response = self.nowApiCall(jwt_payload, "/v1/auth", "POST", jwt=0)
            jwtoken = jwt_response.json()["token"]
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
            response = requests.post(
                server_url, json=payload, headers=headers, timeout=20
            )
        else:
            raise ValueError(f"Unsupported method {method}")

        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]

        _logger.info(
            "NOWPayments %s %s -> %s %s",
            method,
            server_url,
            response.status_code,
            body,
        )
        return response

    def _now_find_payment(self, tx_sudo, payments):
        invoice_id = tx_sudo.provider_invoice_id
        for payment in payments:
            if payment.get("order_id") != tx_sudo.reference:
                continue
            if invoice_id and payment.get("invoice_id") not in (None, invoice_id):
                continue
            return payment
        return None

    def _now_build_notification_data(self, payment, tx_sudo):
        crypto_amount = self._now_float(
            payment.get("actually_paid") or payment.get("pay_amount")
        )
        price_amount = self._now_float(payment.get("price_amount") or tx_sudo.amount)
        crypto_rate = (
            self._now_float(payment.get("crypto_rate"))
            if payment.get("crypto_rate")
            else 0.0
        )
        if not crypto_rate and crypto_amount and price_amount:
            crypto_rate = price_amount / crypto_amount if crypto_amount else 0.0

        settlement_date = fields.Date.to_date(payment.get("updated_at"))
        if not settlement_date:
            settlement_date = fields.Date.to_date(payment.get("created_at"))

        return {
            "payment_status": payment.get("payment_status"),
            "provider_payment_id": payment.get("payment_id") or payment.get("id"),
            "provider_invoice_id": payment.get("invoice_id")
            or tx_sudo.provider_invoice_id,
            "provider_payout_id": payment.get("payout_id"),
            "crypto_currency": payment.get("pay_currency") or payment.get("currency"),
            "crypto_amount": crypto_amount,
            "price_currency": payment.get("price_currency")
            or tx_sudo.currency_id.name,
            "price_amount": price_amount,
            "crypto_rate": crypto_rate,
            "settlement_date": settlement_date,
            "crypto_payment_link": payment.get("invoice_url")
            or tx_sudo.crypto_payment_link,
        }

    @route(_create_invoice_url, type="http", auth="public", methods=["POST"], csrf=False)
    def create_invoice(self, **post):
        """Create a NowPayments invoice."""
        _logger.info("Called create_invoice with data: %s", post)
        trn = request.env["payment.transaction"].sudo().search(
            [("reference", "=", post["reference"]), ("provider_code", "=", "now")],
            limit=1,
        )

        crypto_details = request.env["payment.provider"].sudo().search(
            [("code", "=", "now")], limit=1
        )
        crypto_min_amount = crypto_details.crypto_min_amount
        crypto_max_amount = crypto_details.crypto_max_amount

        amount = float(post["amount"])
        if amount < crypto_min_amount or amount > crypto_max_amount:
            _logger.warning("Amount %s outside allowed range.", amount)
            return request.redirect("/shop/payment")

        web_base_url = request.env["ir.config_parameter"].sudo().get_param(
            "web.base.url"
        )
        success_url = f"{web_base_url}{self._return_url}?ref={post['reference']}"

        payload = {
            "price_amount": amount,
            "price_currency": post["currency_id"],
            "success_url": success_url,
            "order_id": post["reference"],
        }
        api_response = self.nowApiCall(payload, "/v1/invoice", "POST")
        api_response_json = api_response.json()

        if api_response.status_code == 200:
            payment_method = request.env["payment.method"].sudo()._get_from_code(
                "nowpayments"
            )
            trn.write(
                {
                    "provider_invoice_id": api_response_json.get("id"),
                    "crypto_payment_link": api_response_json.get("invoice_url"),
                    "payment_method_id": payment_method.id,
                }
            )
            return request.redirect(api_response_json.get("invoice_url"), local=False)

        _logger.warning("Failed to create NowPayments invoice: %s", api_response.text)
        trn._set_error("Failed to create NowPayments invoice.")
        return request.redirect("/payment/status")

    @route(_return_url, type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def now_return_from_checkout(self, **post):
        # A browser redirect is user-controlled and is never settlement evidence.
        # Verified provider notifications alone advance transaction/accounting state.
        return request.redirect("/payment/status")

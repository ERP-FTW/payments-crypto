# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import requests
import werkzeug
import time
import json
import hashlib
import hmac
import base64
from datetime import datetime, timezone

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError, AccessError



_logger = logging.getLogger(__name__)
TIMEOUT = 10

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [('now', 'Now')]

    # cryptopay server fields
    now_payment_flow = fields.Selection([('payment link','Payment Link'),('direct invoice','Direct Invoice')], string='Payment Flow')
    nowpayments_username = fields.Char(string='NowPayments Email')
    nowpayments_password = fields.Char(string='NowPayments Password')
    now_selected_crypto = fields.Selection([('eth','ETH')], string='Selected Cryptocurrency')

    def call_cryptopay_api(self,payload,api,method,jwt=0):
        try:
            request_url = f"{self.server_url}{api}"
            if jwt == 0:
                headers = {"x-api-key": (self.api_key), "Content-Type": "application/json"}
            if jwt == 1:
                jwt_payload = {"email": self.nowpayments_username,
                               "password": self.nowpayments_password}
                jwt_response = self.call_cryptopay_api(jwt_payload, '/v1/auth', 'POST', 0)
                _logger.info(jwt_response.json())
                jwtoken = jwt_response.json()['token']
                headers = {"x-api-key": (self.api_key), "Content-Type": "application/json", "Authorization": "Bearer " + jwtoken}
            _logger.info(f"value of server_url is {request_url} and method is {method} and header is {headers}")
            if method == "GET":
                apiRes=requests.get(request_url,headers=headers)
            elif method == "POST":
                apiRes = requests.post(request_url, data=json.dumps(payload), headers=headers)
            _logger.info(apiRes.status_code)
            _logger.info(apiRes.json())
            return apiRes
        except Exception as e:
            _logger.info("API call failure: %s", e.args)
            raise UserError(_("API call failure: %s", e.args))

    def _test_connection(self):
        if self.use_payment_terminal == 'now':
            return self.call_cryptopay_api({},"/v1/sub-partner","GET", 1)
        else:
            return super()._test_connection()

    def create_crypto_invoice_payment_link(self, args):
        payload = {
            "price_amount": args['amount'],
            "price_currency": "USD",
            "order_id": args['order_id'],}
        _logger.info(payload)
        create_invoice_api = self.call_cryptopay_api(payload, '/v1/invoice', 'POST')
        if create_invoice_api.status_code != 200:
            return {"code": create_invoice_api.status_code}
        create_invoice_json = create_invoice_api.json()
        inv_json = {
            "code": 0,
            "invoice_id": create_invoice_json['id'],
            "invoice": create_invoice_json['invoice_url'],}
        return inv_json

    def create_crypto_invoice_direct_invoice(self, args,now_selected_crypto):
        payload = {
            "price_amount": args['amount'],
            "price_currency": "USD",
            "pay_currency": now_selected_crypto,
            "order_id": args['order_id'],}
        _logger.info(payload)
        create_invoice_api = self.call_cryptopay_api(payload, '/v1/payment', 'POST')
        if create_invoice_api.status_code != 201:
            return {"code": create_invoice_api.status_code}
        create_invoice_json = create_invoice_api.json()
        inv_json = {
            "code": 0,
            "invoice_id": create_invoice_json['payment_id'],
            "invoice": create_invoice_json['pay_address'],
            "crypto_amt": create_invoice_json['pay_amount'],}
        return inv_json

    @api.model
    def create_crypto_invoice(self, args):
        cryptopay_pm = self.env['pos.payment.method'].search([('id', '=', args['pm_id'])], limit=1)
        if cryptopay_pm.use_payment_terminal != 'now':
            return super().create_crypto_invoice(args)
        now_payment_flow = cryptopay_pm['now_payment_flow']
        if now_payment_flow == 'direct invoice':
            now_selected_crypto = cryptopay_pm['now_selected_crypto']
            create_invoice_api = cryptopay_pm.create_crypto_invoice_direct_invoice(args,now_selected_crypto)
            return create_invoice_api
        else:
            create_invoice_api = cryptopay_pm.create_crypto_invoice_payment_link(args)
            return create_invoice_api

    def check_payment_status_payment_link(self, args):
        cryptopay_pm = self.env['pos.payment.method'].search([('id', '=', args['pm_id'])], limit=1)
        if cryptopay_pm.use_payment_terminal != 'now':
            return super().check_payment_status(args)
        invoice_status_api = cryptopay_pm.call_cryptopay_api({}, '/v1/payment/?limit=10&page=0&sortBy=created_at&orderBy=desc', 'GET', 1)
        if invoice_status_api.status_code != 200:
            return false
        resJson = invoice_status_api.json()['data']
        for payment in resJson:
            _logger.info(f"invoice is {payment.get('order_id')} order is {args['order_id']}")
            if payment.get('order_id') == args['order_id'] and payment.get('payment_status') == "waiting":
                _logger.info(f"payment is {payment}")
                return payment
        return false

    def check_payment_status_direct_invoice(self, args):
        cryptopay_pm = self.env['pos.payment.method'].search([('id', '=', args['pm_id'])], limit=1)
        if cryptopay_pm.use_payment_terminal != 'now':
            return super().check_payment_status(args)
        invoice_status_api = cryptopay_pm.call_cryptopay_api({}, '/v1/payment/' + args.get('invoice_id'), 'GET')
        if invoice_status_api.status_code != 200:
            return false
        return invoice_status_api.json()

    @api.model 
    def check_payment_status(self, args):
        _logger.info(f"passed args are {args}")
        cryptopay_pm = self.env['pos.payment.method'].search([('id', '=', args['pm_id'])], limit=1)
        if cryptopay_pm.use_payment_terminal != 'now':
            return super().check_payment_status(args)
        if cryptopay_pm.now_payment_flow == 'direct invoice':
            check_payment_api = cryptopay_pm.check_payment_status_direct_invoice(args)
            return check_payment_api
        else:
            check_payment_api = cryptopay_pm.check_payment_status_payment_link(args)
            return check_payment_api


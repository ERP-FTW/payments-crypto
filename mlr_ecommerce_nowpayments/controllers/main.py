# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import requests
import json

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


# TODO
# auth should be public or something else for create invoice?

class CustomController(Controller):
    _return_url = '/payment/now/return'
    _create_invoice = '/payment/now/createInvoice'

    def nowApiCall(self, payload, api, method, jwt=0):
        try:
            _logger.info(f"Called now nowApiCall. Passed args are {payload}")
            crypto_details = request.env['payment.provider'].sudo().search([('code', '=', 'now')])
            base_url = crypto_details.mapped('crypto_server_url')[0]
            api_key = crypto_details.mapped('crypto_api_key')[0]
            #store_id = crypto_details.mapped('now_store_id')[0]
            server_url = f"{base_url}{api}"
            if jwt == 0:
                headers = {"x-api-key": (api_key), "Content-Type": "application/json"}
            if jwt == 1:
                jwt_payload = {"email": crypto_details.mapped('nowpayments_username')[0],
                               "password": crypto_details.mapped('nowpayments_password')[0]}
                jwt_response = self.nowApiCall(jwt_payload, '/v1/auth', 'POST', 0)
                jwtoken = jwt_response.json()['token']
                headers = {"x-api-key": (api_key), "Content-Type": "application/json",
                           "Authorization": "Bearer " + jwtoken}
            #headers = {"Authorization": "Bearer %s" % (api_key), "Content-Type": "application/json", "Accept": "application/json"}
            _logger.info(f"value of server_url is {server_url}, method is {method}, and payload is {payload}")
            if method == "GET":
                apiRes = requests.get(server_url, headers=headers)
            elif method == "POST":
                apiRes = requests.post(server_url, data=json.dumps(payload), headers=headers)
            _logger.info(f"Completed now nowApiCall. Passing back {apiRes.json()}")
            return apiRes
        except:
            _logger.info(f"An exception occurred with now nowApiCall.")
            return

    @route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def custom_process_transaction(self, **post):
        try:
            _logger.info(f"Called now custom_process_transaction. Passed args are {post}")
            trn = request.env['payment.transaction'].sudo().search([('reference', '=', post['ref']),('provider_code', '=', 'now')])
            apiRes = self.nowApiCall({}, '/v1/payment/?limit=10&page=0&sortBy=created_at&orderBy=desc', 'GET', 1)
            _logger.info(f"api response from return is {apiRes.json()}")
            payment_method_line = journal.inbound_payment_method_line_ids[:1] if journal else None                            
            payment_method = request.env['payment.method'].sudo()._get_from_code('nowpayments')
            _logger.info(f"Called now payment method. Passed args are {payment_method_line} {payment_method}")
            if apiRes.status_code == 200:
                resJson = apiRes.json()['data']
                for payment in resJson:
                    _logger.info(f"payment is {payment}")
                    if payment.get('order_id') == post['ref']:
                        if payment.get('payment_status') == "finished" or payment.get('payment_status') == "confirmed" or payment.get('payment_status') == "sending":
                            payment_method = request.env['payment.method'].sudo()._get_from_code('nowpayments')
                            trn.write({
                                'crypto_invoice_id': payment.get('payment_id'),
                                'crypto_invoiced_crypto_amount': float(payment.get('outcome_amount')),
                                'payment_method_id': payment_method.id if payment_method else None,})
                            #trn._set_done()
                            _logger.info(f"{post['ref']} order confirmed")
                            return request.redirect('/payment/status')
                _logger.info(f"Issue now custom_process_transaction")
                trn._set_error(f"Payment failed!, NowPayments")
                return request.redirect('/payment/status')
            else:
                _logger.info(f"Issue while checking now invoice, retry after sometime, if issue persists, please contact support or write to us. Issue response code {apiRes.status_code}")
                trn._set_error(f"Issue while checking now invoice, retry after sometime, if issue persists, please contact support or write to us. Issue response code {apiRes.status_code}")
            _logger.info(f"Completed now custom_process_transaction. Passing back {apiRes.json()}")
            return request.redirect('/payment/status')
        except:
            _logger.info(f"An exception occurred with now custom_process_transaction.")
            trn._set_error(f"Issue while checking now invoice, retry after sometime, if issue persists, please contact support. An exception occurred in now custom_process_transaction,")
            return request.redirect('/payment/status')

    @route(_create_invoice, type='http', auth='public', methods=['POST'], csrf=False)
    def create_invoice(self, **post):
        try:
            _logger.info(f"Called now create_invoice. Passed args are {post}")
            trn = request.env['payment.transaction'].sudo().search([('reference', '=', post['ref']), ('provider_code', '=', 'now')])
            crypto_details = request.env['payment.provider'].sudo().search([('code', '=', 'now')])
            crypto_min_amount = crypto_details.mapped('crypto_min_amount')[0]
            crypto_max_amount = crypto_details.mapped('crypto_max_amount')[0]
            if float(post['amount']) <= crypto_min_amount or float(post['amount']) >= crypto_max_amount:
                #return {"type": "ir.actions.client","tag": "display_notification","params": {"title": "below min","message": "below amount","sticky": False,"type": "danger"}
                return request.redirect('/shop/payment')
            web_base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            checkout = f"{web_base_url}/payment/now/return?ref={post['ref']}"
            payload = {
            "price_amount": post['amount'],
            "price_currency": post['currency'],
            "success_url": checkout,
            "order_id": post['ref']}
            apiRes = self.nowApiCall(payload, '/v1/invoice', 'POST')
            apiRes_json = apiRes.json()
            if apiRes.status_code == 200:
                trn.write({'crypto_invoice_id': apiRes_json.get('id')})
                _logger.info(f"Completed now create_invoice. Passing back {apiRes_json.get('invoice_url')}")
                return request.redirect(apiRes_json.get('invoice_url'), local=False)
            else:
                trn = request.env['payment.transaction'].sudo().search([('reference', '=', post['ref']), ('provider_code', '=', 'now')])
                _logger.info("Issue while creating now invoice, retry after sometime, if issue persists, please contact support or write to us")
                trn._set_error("Issue while creating now invoice, retry after sometime, if issue persists, please contact support or write to us")
                return request.redirect('/payment/status')
        except:
            _logger.info("Issue while creating now invoice, retry after sometime, if issue persists, please contact support. An exception occurred in now create_invoice")
            trn._set_error("Issue while creating now invoice, retry after sometime, if issue persists, please contact support. An exception occurred in now create_invoice")
            return request.redirect('/payment/status')

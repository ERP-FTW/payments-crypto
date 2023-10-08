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
    _return_url = '/payment/btcpay/return'
    _create_invoice = '/payment/btcpay/createInvoice'

    def btcpayApiCall(self, payload, api, method, jwt):
        _logger.info("API CALL")
        #try:
        btcpay_details = request.env['payment.provider'].sudo().search([('code', '=', 'btcpay')])
        base_url = btcpay_details.mapped('btcpay_server_url')[0]
        store_id = btcpay_details.mapped('btcpay_store_id')[0]
        api_key = btcpay_details.mapped('btcpay_api_key')[0]
        server_url = f"{base_url}{api.format(store_id=store_id)}"
        if jwt == 0:
            headers = {"x-api-key": (api_key), "Content-Type": "application/json"}
        if jwt == 1:
            jwt_payload = {"email":btcpay_details.mapped('nowpayments_username')[0],
                           "password":btcpay_details.mapped('nowpayments_password')[0]}
            jwt_response = self.btcpayApiCall(jwt_payload, '/v1/auth', 'POST', 0)
            _logger.info(jwt_response.json())
            jwtoken = jwt_response.json()['token']
            headers = {"x-api-key": (api_key), "Content-Type": "application/json", "Authorization": "Bearer " + jwtoken}
        _logger.info(f"value of server_url is {server_url} and method is {method} and header is {headers}")
        if method == "GET":
            apiRes = requests.get(server_url, headers=headers)
        elif method == "POST":
            apiRes = requests.post(server_url, data=json.dumps(payload), headers=headers)
        _logger.info(apiRes)
        return apiRes


    @route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def custom_process_transaction(self, **post):
        _logger.info('custom process of transaction')
        trn = request.env['payment.transaction'].sudo().search(
            [('reference', '=', post['ref']), ('provider_code', '=', 'btcpay')])
        btcpay_invoice_id = trn.mapped('btcpay_invoice_id')[0]
        _logger.info(trn)
        _logger.info(btcpay_invoice_id)
        apiRes = self.btcpayApiCall({}, '/v1/payment/?limit=10&page=0&sortBy=created_at&orderBy=desc', 'GET', 1)
        _logger.info(post)
        _logger.info(apiRes.status_code)
        _logger.info(f"api respnse from return is {apiRes.json()}")
        if apiRes.status_code == 200:
            resJson = apiRes.json()['data']
            for payment in resJson:
                _logger.info(f"payment is {payment}")
                if payment.get('order_id') == post['ref'] and payment.get('payment_status') == "confirmed":
                    sats = float(payment.get('outcome_amount'))
                    trn.write({
                        'btcpay_invoice_id': payment.get('payment_id'),
                        #'btcpay_payment_link': payment.get('checkoutLink'),
                        'btcpay_invoiced_sat_amount': sats,})
                    trn._set_done()
                    _logger.info("order confirmed")
                    return request.redirect('/payment/status')
                elif payment.get('order_id') == post['ref'] and payment.get('payment_status') == "waiting":
                    sats = float(payment.get('outcome_amount'))
                    trn.write({
                        'btcpay_invoice_id': payment.get('payment_id'),
                        #'btcpay_payment_link': payment.get('checkoutLink'),
                        'btcpay_invoiced_sat_amount': sats,})
                    trn._set_done()
                    _logger.info("order waiting")
                    return request.redirect('/payment/status')
                else:
                    _logger.info("order something else")
                    #trn._set_error(f"Payment failed!, Nodeless Invoice status: {resJson[0]['status']}")
        else:
            trn._set_error(
                "Issue while checking Nodeless invoice, retry after sometime, if issue persits, please contact support or write to us")

        return request.redirect('/payment/status')

    @route(_create_invoice, type='http', auth='public', methods=['POST'], csrf=False)
    def create_invoice(self, **post):
        _logger.info("Inside create_invoice")
        _logger.info(post)
        web_base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        _logger.info(web_base_url)
        checkout = f"{web_base_url}/payment/btcpay/return?ref={post['ref']}"

        payload = {
            "price_amount": post['amount'],
            "price_currency": post['currency'],
            "success_url": checkout,
            "order_id": post['ref']
        }

        _logger.info("request payload")
        _logger.info(json.dumps(payload))

        apiRes = self.btcpayApiCall(payload, '/v1/invoice', 'POST',0)
        _logger.info(f"response from api call {apiRes.json()}")
        apiRes_json = apiRes.json()
        _logger.info(f"response from api call {apiRes}")

        if apiRes.status_code == 200:
            trn = request.env['payment.transaction'].sudo().search([('reference', '=', post['ref']), ('provider_code', '=', 'btcpay')])
            trn.write({'btcpay_invoice_id': apiRes_json.get('id')})
            _logger.info(trn)
            _logger.info({'btcpay_invoice_id': apiRes_json.get('id')})
            return request.redirect(apiRes_json.get('invoice_url'), local=False)
        else:
            trn = request.env['payment.transaction'].sudo().search(
                [('reference', '=', post['ref']), ('provider_code', '=', 'btcpay')])
            trn._set_error(
                "Issue while creating Nodeless invoice, retry after sometime, if issue persits, please contact support or write to us")
            return request.redirect('/payment/status')

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

    def btcpayApiCall(self, payload, api, method):
        try:
            _logger.info(f"Called BTCPay btcpayApiCall. Passed args are {payload}")
            crypto_details = request.env['payment.provider'].sudo().search([('code', '=', 'btcpay')])
            base_url = crypto_details.mapped('crypto_server_url')[0]
            api_key = crypto_details.mapped('crypto_api_key')[0]
            store_id = crypto_details.mapped('btcpay_store_id')[0]
            server_url = f"{base_url}{api.format(store_id=store_id)}"
            headers = { "Authorization": f"Token {api_key}", "Content-Type": "application/json"}
            _logger.info(f"value of server_url is {server_url}, method is {method}, and payload is {payload}")
            if method == "GET":
                apiRes = requests.get(server_url, headers=headers)
            elif method == "POST":
                apiRes = requests.post(server_url, data=json.dumps(payload), headers=headers)
            _logger.info(f"Completed BTCPay btcpayApiCall. Passing back {apiRes.json()}")
            return apiRes
        except Exception as e:
            _logger.info(f"An exception occurred with BTCPay btcpayApiCall: {e}")
            return

    @route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def custom_process_transaction(self, **post):
        try:
            _logger.info(f"Called BTCPay custom_process_transaction. Passed args are {post}")
            trn = request.env['payment.transaction'].sudo().search([('reference', '=', post['ref']),('provider_code', '=', 'btcpay')])
            trn_amount = trn.mapped('amount')[0]
            apiRes = self.btcpayApiCall({}, '/api/v1/stores/{store_id}/invoices?textsearch=' + post['ref'], 'GET')
            _logger.info(f"api response from return is {apiRes.json()}")
            if apiRes.status_code == 200:
                resJson = apiRes.json()#['data']
                if resJson[0]['status'] == "Settled":
                    apiRes2 = self.btcpayApiCall({}, '/api/v1/stores/{store_id}/invoices/' + resJson[0][
                        'id'] + '/payment-methods', 'GET')
                    if apiRes2.status_code == 200:
                        resJson2 = apiRes2.json()
                        crypto_invoiced_crypto_amount = float(resJson2[0]['paymentMethodPaid'])
                        btcpay_invoiced_sat_amount = crypto_invoiced_crypto_amount*100000000
                        conversion_rate = float(resJson2[0]['rate'])
                        trn.write({
                            'crypto_payment': 'true',
                            'crypto_payment_type': resJson2[0]['cryptoCode'],
                            'crypto_conversion_rate': conversion_rate,
                            'crypto_payment_link': resJson[0]['checkoutLink'],
                            'crypto_invoiced_crypto_amount': crypto_invoiced_crypto_amount,
                            'btcpay_invoiced_sat_amount': btcpay_invoiced_sat_amount,})
                        trn._set_done()
                else:
                    _logger.info(f"Issue BTCPay custom_process_transaction, status is  Passing back {resJson['status']}")
                    trn._set_error(f"Payment failed!, BTCPay Invoice status: {resJson['status']}")
            else:
                _logger.info(f"Issue while checking BTCPay invoice, retry after sometime, if issue persits, please contact support or write to us. Issue response code {apiRes.status_code}")
                trn._set_error(f"Issue while checking BTCPay invoice, retry after sometime, if issue persits, please contact support or write to us. Issue response code {apiRes.status_code}")
            _logger.info(f"Completed BTCPay custom_process_transaction. Passing back {apiRes.json()}")
            return request.redirect('/payment/status')
        except Exception as e:
            _logger.info(f"An exception occurred with BTCPay custom_process_transaction: {e}")
            trn._set_error(f"Issue while checking BTCPay invoice, retry after sometime, if issue persists, please contact support. An exception occurred in BTCPay custom_process_transaction: {e}")
            return request.redirect('/payment/status')

    @route(_create_invoice, type='http', auth='public', methods=['POST'], csrf=False)
    def create_invoice(self, **post):
        try:
            _logger.info(f"Called BTCPay create_invoice. Passed args are {post}")
            trn = request.env['payment.transaction'].sudo().search([('reference', '=', post['ref']), ('provider_code', '=', 'btcpay')])
            crypto_details = request.env['payment.provider'].sudo().search([('code', '=', 'btcpay')])
            crypto_min_amount = crypto_details.mapped('crypto_min_amount')[0]
            crypto_max_amount = crypto_details.mapped('crypto_max_amount')[0]
            if float(post['amount']) < crypto_min_amount or float(post['amount']) > crypto_max_amount:
                #return {"type": "ir.actions.client","tag": "display_notification","params": {"title": "below min","message": "below amount","sticky": False,"type": "danger"}
                return request.redirect('/shop/payment')
            web_base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            redirectURL = f"{web_base_url}/payment/btcpay/return?ref={post['ref']}"
            checkout = {
                "redirectURL": redirectURL,
                "paymentMethods": ["BTC", "BTC-LightningNetwork"]
            }
            payload = {
                "amount": post['amount'],
                "checkout": checkout,
                "currency": post['currency'],
                "additionalSearchTerms": [post['ref']]}
            apiRes = self.btcpayApiCall(payload, '/api/v1/stores/{store_id}/invoices', 'POST')
            apiRes_json = apiRes.json()#['data']
            if apiRes.status_code == 200:
                trn.write({'crypto_invoice_id': apiRes_json.get('id')})
                _logger.info(f"Completed BTCPay create_invoice. Passing back {apiRes_json.get('checkoutLink')}")
                return request.redirect(apiRes_json.get('checkoutLink'), local=False)
            else:
                trn = request.env['payment.transaction'].sudo().search([('reference', '=', post['ref']), ('provider_code', '=', 'btcpay')])
                _logger.info("Issue while creating BTCPay invoice, retry after sometime, if issue persists, please contact support or write to us")
                trn._set_error("Issue while creating BTCPay invoice, retry after sometime, if issue persists, please contact support or write to us")
                return request.redirect('/payment/status')
        except Exception as e:
            _logger.info(f"Issue while creating BTCPay invoice, retry after sometime, if issue persists, please contact support. An exception occurred in BTCPay create_invoice: {e}")
            trn._set_error(f"Issue while creating BTCPay invoice, retry after sometime, if issue persists, please contact support. An exception occurred in BTCPay create_invoice{e}")
            return request.redirect('/payment/status')
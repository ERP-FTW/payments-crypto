import json

from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response


class NOWPaymentsIPNController(http.Controller):
    @http.route("/payment/nowpayments/ipn/<string:provider_uuid>", type="http", auth="public", methods=["POST"], csrf=False)
    def nowpayments_ipn(self, provider_uuid, **kwargs):
        provider = request.env["crypto.transfer.provider"].sudo().search([("provider_uuid", "=", provider_uuid), ("active", "=", True)], limit=1)
        if not provider:
            return Response("Unknown or inactive provider", status=404)
        signature = request.httprequest.headers.get("x-nowpayments-sig")
        if not signature:
            return Response("Missing signature", status=401)
        try:
            payload = json.loads(request.httprequest.get_data(cache=False, as_text=True))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response("Malformed JSON", status=400)
        if not isinstance(payload, dict):
            return Response("JSON object required", status=400)
        event, duplicate = provider.process_signed_ipn(payload, signature)
        if not event.signature_verified:
            return Response("Invalid signature", status=401)
        return Response("duplicate" if duplicate else "ok", status=200)

    @http.route("/payment/nowpayments/return", type="http", auth="public", methods=["GET"], csrf=False)
    def nowpayments_return(self, reference=None, **kwargs):
        # Browser navigation is never evidence of settlement.  The standard status
        # page only displays state already established by a verified IPN.
        return request.redirect("/payment/status")

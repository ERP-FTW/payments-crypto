import logging
from datetime import timedelta

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class CryptoCashoutProvider(models.Model):
    _inherit = "crypto.cashout.provider"

    code = fields.Selection(
        selection_add=[("nowpayments_fiat_payout", "NowPayments Fiat Payouts")], 
        ondelete={"nowpayments_fiat_payout": "set default"},
    )

    nowpayments_api_base_url = fields.Char(default="https://api.nowpayments.io/v1")
    nowpayments_api_key = fields.Char(string="NowPayments API Key")
    nowpayments_email = fields.Char(string="NowPayments Email")
    nowpayments_password = fields.Char(string="NowPayments Password")
    nowpayments_jwt_token = fields.Char(string="NowPayments JWT Token", copy=False)
    nowpayments_token_updated_at = fields.Datetime(copy=False)
    nowpayments_timeout = fields.Integer(default=30)

    def _ensure_nowpayments_provider(self):
        self.ensure_one()
        if self.code != "nowpayments_fiat_payout":
            raise UserError(
                _(
                    "Provider %(provider)s is not configured for NowPayments fiat payouts."
                )
                % {"provider": self.display_name}
            )

    def _ensure_nowpayments_token(self):
        self.ensure_one()
        self._ensure_nowpayments_provider()
        if not self.nowpayments_jwt_token:
            self.provider_authenticate()
            return
        if self.nowpayments_token_updated_at:
            age = fields.Datetime.now() - self.nowpayments_token_updated_at
            if age > timedelta(minutes=30):
                self.provider_authenticate()

    def _nowpayments_request(self, method, path, json=None, params=None, skip_auth=False):
        self.ensure_one()
        self._ensure_nowpayments_provider()
        if not skip_auth:
            self._ensure_nowpayments_token()
        base_url = (self.nowpayments_api_base_url or "").rstrip("/")
        if not base_url:
            raise UserError(_("NowPayments API base URL is required."))
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{base_url}{normalized_path}"
        headers = {"Content-Type": "application/json"}
        if self.nowpayments_api_key:
            headers["x-api-key"] = self.nowpayments_api_key
        if self.nowpayments_jwt_token and not skip_auth:
            headers["Authorization"] = f"Bearer {self.nowpayments_jwt_token}"
        timeout = self.nowpayments_timeout or 30
        try:
            response = requests.request(
                method=method,
                url=url,
                json=json,
                params=params,
                headers=headers,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            _logger.exception("NowPayments request failed: %s %s", method, url)
            raise UserError(
                _("NowPayments request failed: %(error)s") % {"error": str(exc)}
            ) from exc

        if not response.ok:
            message = response.text or _("No response body provided.")
            raise UserError(
                _(
                    "NowPayments API error %(status)s on %(path)s: %(message)s"
                )
                % {
                    "status": response.status_code,
                    "path": normalized_path,
                    "message": message,
                }
            )
        try:
            return response.json()
        except ValueError as exc:
            raise UserError(
                _("NowPayments returned an invalid JSON response for %(path)s.")
                % {"path": normalized_path}
            ) from exc

    def provider_authenticate(self):
        self.ensure_one()
        self._ensure_nowpayments_provider()
        if not self.nowpayments_email or not self.nowpayments_password:
            raise UserError(
                _("NowPayments email and password are required for authentication.")
            )
        payload = {
            "email": self.nowpayments_email,
            "password": self.nowpayments_password,
        }
        response = self._nowpayments_request("POST", "/auth", json=payload, skip_auth=True)
        token = response.get("token") or response.get("jwt_token")
        if not token:
            raise UserError(_("NowPayments authentication did not return a token."))
        self.write(
            {
                "nowpayments_jwt_token": token,
                "nowpayments_token_updated_at": fields.Datetime.now(),
            }
        )
        return token

    def provider_get_balance(self):
        self.ensure_one()
        self._ensure_nowpayments_provider()
        return self._nowpayments_request("GET", "/balance")

    def _nowpayments_prepare_withdrawals_payload(self, payout):
        withdrawals_payload = []
        for withdrawal in payout.withdrawal_ids:
            if not withdrawal.address:
                raise UserError(_("Withdrawal address is required."))
            if withdrawal.amount <= 0:
                raise UserError(_("Withdrawal amount must be strictly positive."))
            currency_code = (withdrawal.currency_code or payout.crypto_currency_id.name or "").lower()
            if not currency_code:
                raise UserError(_("Withdrawal currency code is required."))
            entry = {
                "address": withdrawal.address,
                "currency": currency_code,
                "amount": withdrawal.amount,
            }
            if withdrawal.extra_id:
                entry["extra_id"] = withdrawal.extra_id
            withdrawals_payload.append(entry)
        if not withdrawals_payload:
            raise UserError(_("At least one withdrawal line is required."))
        return withdrawals_payload

    def _nowpayments_find_withdrawal_line(self, payout, data):
        provider_id = data.get("id")
        if provider_id:
            match = payout.withdrawal_ids.filtered(
                lambda w: w.provider_withdrawal_id == str(provider_id)
            )
            if match:
                return match[:1]
        address = data.get("address")
        currency_code = (data.get("currency") or "").upper()
        amount = data.get("amount")
        if address and currency_code and amount is not None:
            rounding = payout.crypto_currency_id.rounding or 0.00000001
            for line in payout.withdrawal_ids:
                if line.address != address:
                    continue
                if (line.currency_code or "").upper() != currency_code:
                    continue
                if float_compare(line.amount, amount, precision_rounding=rounding) != 0:
                    continue
                return line
        return payout.withdrawal_ids[:0]

    def _nowpayments_prepare_withdrawal_vals(self, payout, data):
        currency_code = (data.get("currency") or payout.crypto_currency_id.name or "").upper()
        currency = payout.crypto_currency_id
        return {
            "payout_id": payout.id,
            "currency_code": currency_code,
            "currency_id": currency.id if currency else False,
            "amount": data.get("amount") or 0.0,
            "address": data.get("address") or False,
            "extra_id": data.get("extra_id") or data.get("extraId"),
            "provider_withdrawal_id": str(data.get("id")) if data.get("id") else False,
            "batch_withdrawal_id": data.get("batchWithdrawalId") or data.get("batch_withdrawal_id"),
            "status": data.get("status"),
            "tx_hash": data.get("hash") or data.get("txHash"),
            "error": data.get("error"),
            "created_at": data.get("createdAt") or data.get("created_at"),
            "requested_at": data.get("requestedAt") or data.get("requested_at"),
            "updated_at": data.get("updatedAt") or data.get("updated_at"),
        }

    def _nowpayments_upsert_withdrawals(self, payout, withdrawals_data):
        withdrawal_model = self.env["crypto.cashout.withdrawal"]
        for data in withdrawals_data:
            line = self._nowpayments_find_withdrawal_line(payout, data)
            vals = self._nowpayments_prepare_withdrawal_vals(payout, data)
            if line:
                line.write({k: v for k, v in vals.items() if v not in (False, None, "")})
            else:
                withdrawal_model.create(vals)

    def provider_create_payout(self, payout):
        self.ensure_one()
        self._ensure_nowpayments_provider()
        payout._ensure_withdrawals_currency()
        payload = {"withdrawals": self._nowpayments_prepare_withdrawals_payload(payout)}
        response = self._nowpayments_request("POST", "/payout", json=payload)
        provider_payout_id = response.get("id") or response.get("payout_id")
        if not provider_payout_id:
            raise UserError(_("NowPayments did not return a payout ID."))
        now = fields.Datetime.now()
        payout.write(
            {
                "provider_payout_id": str(provider_payout_id),
                "requested_at": payout.requested_at or now,
                "created_at": payout.created_at or now,
                "updated_at": now,
                "state": "processing",
            }
        )
        withdrawals_data = response.get("withdrawals") or []
        if withdrawals_data:
            self._nowpayments_upsert_withdrawals(payout, withdrawals_data)
        return True

    def _nowpayments_compute_payout_state(self, payout):
        statuses = {((line.status or "").lower()) for line in payout.withdrawal_ids}
        statuses.discard("")
        if not statuses:
            return "processing"
        failed_statuses = {"failed", "error", "rejected"}
        done_statuses = {
            "finished",
            "confirmed",
            "success",
            "sent",
            "done",
            "completed",
        }
        if statuses & failed_statuses:
            return "failed"
        if statuses.issubset(done_statuses):
            return "done"
        return "processing"

    def provider_get_payout(self, payout):
        self.ensure_one()
        self._ensure_nowpayments_provider()
        if not payout.provider_payout_id:
            raise UserError(_("Provider payout ID is required to refresh the payout."))
        response = self._nowpayments_request(
            "GET", f"/payout/{payout.provider_payout_id}"
        )
        now = fields.Datetime.now()
        payout_vals = {
            "updated_at": now,
        }
        if response.get("createdAt"):
            payout_vals.setdefault("created_at", response.get("createdAt"))
        if response.get("requestedAt"):
            payout_vals.setdefault("requested_at", response.get("requestedAt"))
        payout.write(payout_vals)
        withdrawals_data = response.get("withdrawals") or []
        if withdrawals_data:
            self._nowpayments_upsert_withdrawals(payout, withdrawals_data)
        payout.state = self._nowpayments_compute_payout_state(payout)
        return True

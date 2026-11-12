/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

const UNPAID = new Set(["waiting", "not_found", "found"]);
const PENDING = new Set(["confirming", "confirmed", "sending"]);
const DISPUTED = new Set(["partially_paid", "refunded"]);
const FAILED = new Set(["expired", "failed"]);

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        for (const line of this.paymentLines) {
            if (!line.is_crypto_payment || line.payment_method_id.use_payment_terminal !== "now") {
                continue;
            }
            let response;
            try {
                response = await this.env.services.orm.silent.call(
                    "pos.payment.method",
                    "now_check_payment_status",
                    [{
                        invoice_id: line.cryptopay_invoice_id,
                        pm_id: line.payment_method_id.id,
                        order_id: this.currentOrder.uuid,
                    }]
                );
            } catch (error) {
                return false;
            }
            const status = response.payment_status;
            if (status === "finished") {
                line.invoiced_crypto_amount = response.pay_amount;
                line.cryptopay_payment_type = response.pay_currency;
                line.conversion_rate = (line.amount / line.invoiced_crypto_amount).toFixed(2);
                line.crypto_payment_status = _t("Invoice Paid");
                line.setPaymentStatus("done");
                continue;
            }
            if (UNPAID.has(status)) {
                this._showNowPaymentsStatus(
                    _t("Payment Request Unpaid"),
                    _t("The customer payment has not been found or completed."),
                    status
                );
                line.setPaymentStatus("waitingCard");
            } else if (PENDING.has(status)) {
                this._showNowPaymentsStatus(
                    _t("Payment Request Pending"),
                    _t("Funds are being transferred and must be confirmed."),
                    status
                );
                line.setPaymentStatus("waitingCard");
            } else if (DISPUTED.has(status)) {
                this._showNowPaymentsStatus(
                    _t("Payment Request Dispute"),
                    _t("A partial payment or refund requires manager review."),
                    status
                );
                line.setPaymentStatus("waitingCard");
            } else if (FAILED.has(status)) {
                this._showNowPaymentsStatus(
                    _t("Payment Request Failed"),
                    _t("Retry by sending a new payment request."),
                    status
                );
                line.setPaymentStatus("retry");
            } else {
                this._showNowPaymentsStatus(
                    _t("Unknown Payment Status"),
                    _t("The payment cannot be validated."),
                    status || _t("missing")
                );
                line.setPaymentStatus("retry");
            }
            return false;
        }
        return super.validateOrder(isForceValidate);
    },

    _showNowPaymentsStatus(title, message, status) {
        this.dialog.add(AlertDialog, {
            title,
            body: _t("%(message)s Status: %(status)s", { message, status }),
        });
    },
});

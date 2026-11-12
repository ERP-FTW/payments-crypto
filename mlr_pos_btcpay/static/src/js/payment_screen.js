/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        for (const line of this.paymentLines) {
            if (!line.is_crypto_payment || line.payment_method_id.use_payment_terminal !== "btcpay") {
                continue;
            }
            let response;
            try {
                response = await this.env.services.orm.silent.call(
                    "pos.payment.method",
                    "btcpay_check_payment_status",
                    [{
                        invoice_id: line.cryptopay_invoice_id,
                        pm_id: line.payment_method_id.id,
                        order_id: this.currentOrder.uuid,
                    }]
                );
            } catch (error) {
                return false;
            }
            if (["Paid", "Settled"].includes(response.status)) {
                line.crypto_payment_status = _t("Invoice Paid");
                line.setPaymentStatus("done");
            } else if (["New", "Unpaid", "Processing"].includes(response.status)) {
                this.dialog.add(AlertDialog, {
                    title: _t("Payment Request Pending"),
                    body: _t("Payment is pending. Retry after the customer confirms payment."),
                });
                line.setPaymentStatus("waitingCard");
                return false;
            } else {
                this.dialog.add(AlertDialog, {
                    title: _t("Payment Request Failed"),
                    body: _t("The BTCPay invoice is expired, invalid, or has an unknown state."),
                });
                line.setPaymentStatus("retry");
                return false;
            }
        }
        return super.validateOrder(isForceValidate);
    },
});

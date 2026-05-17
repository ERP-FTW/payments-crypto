/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const order = this.pos.get_order();
        const paymentLines = order?.payment_ids || this.paymentLines || [];

        for (const line of paymentLines) {
            if (
                line.is_crypto_payment &&
                line.payment_method_id?.use_payment_terminal === "breez" &&
                line.get_payment_status?.() !== "done"
            ) {
                if (!line.cryptopay_invoice_id) {
                    line.update?.({ crypto_payment_status: "Missing Breez invoice" });
                    line.crypto_payment_status = "Missing Breez invoice";
                    line.set_payment_status("retry");

                    this.dialog.add(AlertDialog, {
                        title: _t("Breez Payment Error"),
                        body: _t("No Breez invoice was found for this payment line. Please retry the payment."),
                    });
                    return;
                }

                let apiResp;
                try {
                    if (this.pos.data?.call) {
                        apiResp = await this.pos.data.call("pos.payment.method", "breez_check_payment_status", [
                            {
                                invoice_id: line.cryptopay_invoice_id,
                                pm_id: line.payment_method_id.id,
                                order_id: order.uuid || order.name,
                            },
                        ]);
                    } else {
                        apiResp = await this.env.services.orm.silent.call(
                            "pos.payment.method",
                            "breez_check_payment_status",
                            [{
                                invoice_id: line.cryptopay_invoice_id,
                                pm_id: line.payment_method_id.id,
                                order_id: order.uuid || order.name,
                            }]
                        );
                    }
                } catch (error) {
                    console.error("Breez validation status check failed", error);
                    line.update?.({ crypto_payment_status: "Could not verify Breez payment" });
                    line.crypto_payment_status = "Could not verify Breez payment";
                    line.set_payment_status("retry");

                    this.dialog.add(AlertDialog, {
                        title: _t("Payment Status Error"),
                        body: _t("Could not verify Breez payment status. Please retry."),
                    });
                    return;
                }

                const status = String(apiResp?.status || "").toLowerCase();
                const isPaid =
                    String(apiResp?.code) === "0" &&
                    ["paid", "settled", "complete", "succeeded", "success"].includes(status);

                if (isPaid) {
                    line.update?.({ crypto_payment_status: "Invoice paid" });
                    line.crypto_payment_status = "Invoice paid";
                    line.set_payment_status("done");
                    continue;
                }

                const failedStatuses = ["expired", "invalid", "failed", "error"];
                if (failedStatuses.includes(status)) {
                    line.update?.({ crypto_payment_status: `Breez payment failed: ${status}` });
                    line.crypto_payment_status = `Breez payment failed: ${status}`;
                    line.set_payment_status("retry");

                    this.dialog.add(AlertDialog, {
                        title: _t("Payment Request Failed"),
                        body: `${_t("The Breez payment failed or expired.")} ${_t("Status")}: ${status}`,
                    });
                    return;
                }

                /*
                 * Fail closed. Any non-paid status blocks POS validation.
                 * This includes pending, not_found, unknown, empty status,
                 * inaccessible, or any future Breez status we do not know yet.
                 */
                line.update?.({ crypto_payment_status: `Waiting for Breez payment: ${status || "unknown"}` });
                line.crypto_payment_status = `Waiting for Breez payment: ${status || "unknown"}`;
                line.set_payment_status("cryptowaiting");

                this.dialog.add(AlertDialog, {
                    title: _t("Payment Request Unpaid"),
                    body: `${_t("Breez payment must be confirmed before validating.")} ${_t("Status")}: ${status || "unknown"}`,
                });
                return;
            }
        }

        await super.validateOrder(isForceValidate);
    },
});
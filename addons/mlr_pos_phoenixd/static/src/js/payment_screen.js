/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

function rawJsonToString(rawJson) {
    if (!rawJson) {
        return false;
    }
    if (typeof rawJson === "string") {
        return rawJson;
    }
    return JSON.stringify(rawJson);
}

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        for (const line of this.paymentLines) {
            if (line.is_crypto_payment && line.payment_method_id.use_payment_terminal === "phoenixd") {
                try {
                    const order = this.pos.get_order();
                    if (!order) {
                        return false;
                    }
                    const apiResp = await this.env.services.orm.silent.call(
                        "pos.payment.method",
                        "phoenixd_check_payment_status",
                        [{
                            invoice_id: line.cryptopay_invoice_id,
                            pm_id: line.payment_method_id.id,
                            order_id: order.uuid,
                        }]
                    );
                    const status = (apiResp.status || "").toLowerCase();
                    line.provider_status = apiResp.provider_status || status;
                    line.provider_raw_json = rawJsonToString(apiResp.provider_raw_json);

                    if (status === "paid") {
                        line.crypto_payment_status = "Invoice Paid";
                        line.received_sat_amount = apiResp.received_sat_amount || line.requested_sat_amount;
                        line.provider_fee_sat = apiResp.provider_fee_sat || 0;
                        line.provider_completed_at = apiResp.provider_completed_at || false;
                        line.set_payment_status("done");
                    } else if (status === "pending") {
                        line.crypto_payment_status = "Payment pending";
                        line.set_payment_status("cryptowaiting");
                        return false;
                    } else if (status === "expired") {
                        line.crypto_payment_status = "Invoice Expired";
                        line.set_payment_status("retry");
                        return false;
                    }
                } catch {
                    return false;
                }
            }
        }
        return super.validateOrder(isForceValidate);
    },
});

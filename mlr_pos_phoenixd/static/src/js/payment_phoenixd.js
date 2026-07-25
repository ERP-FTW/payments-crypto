/** @odoo-module */

import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";

const SATS_PER_BTC = 100000000;

function rawJsonToString(rawJson) {
    if (!rawJson) {
        return false;
    }
    if (typeof rawJson === "string") {
        return rawJson;
    }
    return JSON.stringify(rawJson);
}

function amountToBtc(data) {
    if (data.crypto_unit === "sat") {
        return Number(data.crypto_amt || data.requested_sat_amount || 0) / SATS_PER_BTC;
    }
    return Number(data.crypto_amount_currency || data.crypto_amt || 0);
}

export class PaymentPhoenixd extends PaymentInterface {
    async send_payment_request(cid) {
        const order = this.pos.get_order();
        const line = order?.get_selected_paymentline();
        if (!order || !line) {
            return false;
        }

        await super.send_payment_request(...arguments);

        let data;
        try {
            data = await this.env.services.orm.silent.call(
                "pos.payment.method",
                "phoenixd_create_crypto_invoice",
                [{ pm_id: line.payment_method_id.id, amount: line.amount, order_id: order.uuid }]
            );
        } catch {
            line.crypto_payment_status = "Invoice creation failed";
            line.set_payment_status("retry");
            return false;
        }

        if (!data || (data.code !== 0 && data.code !== "0")) {
            line.crypto_payment_status = `Invoice creation failed: ${data?.code || "unknown error"}`;
            line.set_payment_status("retry");
            return false;
        }

        const cryptoAmount = amountToBtc(data);
        line.is_crypto_payment = true;
        line.cryptopay_payment_link = data.cryptopay_payment_link;
        line.cryptopay_invoice_id = data.invoice_id;
        line.invoiced_crypto_amount = cryptoAmount;
        line.crypto_amount_currency = cryptoAmount;
        line.cryptopay_payment_type = data.cryptopay_payment_type;
        line.conversion_rate = data.conversion_rate || data.crypto_rate;
        line.crypto_rate = data.crypto_rate || data.conversion_rate;
        line.fiat_currency_id = data.fiat_currency_id || line.fiat_currency_id;
        line.crypto_currency_id = data.crypto_currency_id || line.crypto_currency_id;
        line.requested_sat_amount = data.requested_sat_amount;
        line.provider_status = data.provider_status;
        line.provider_raw_json = rawJsonToString(data.provider_raw_json);
        line.crypto_payment_status = "Invoice created";

        if (data.cryptopay_payment_link && window.ZXing?.BrowserQRCodeSvgWriter) {
            const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
            const qrCodeSvg = new XMLSerializer().serializeToString(
                codeWriter.write(data.cryptopay_payment_link, 150, 150)
            );
            line.cryptopay_payment_link_qr_code = `data:image/svg+xml;base64,${window.btoa(qrCodeSvg)}`;
        }

        line.set_payment_status("cryptowaiting");
        return this._check_payment_status(line);
    }

    async send_payment_cancel(order, cid) {
        super.send_payment_cancel(...arguments);
    }

    async _check_payment_status(line) {
        const order = this.pos.get_order();
        if (!order) {
            return false;
        }

        try {
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
                return true;
            }
            if (status === "expired") {
                line.crypto_payment_status = "Invoice Expired";
                line.set_payment_status("retry");
                return false;
            }

            line.crypto_payment_status = "Payment pending";
            line.set_payment_status("cryptowaiting");
            return true;
        } catch {
            return false;
        }
    }
}

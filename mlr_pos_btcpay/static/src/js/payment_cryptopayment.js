/** @odoo-module */

import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

const POLL_ATTEMPTS = 100;
const POLL_DELAY_MS = 50000;

export class PaymentBTCPay extends PaymentInterface {
    async sendPaymentRequest(uuid) {
        await super.sendPaymentRequest(...arguments);
        const order = this.pos.getOrder();
        const line = order?.payment_ids.find((payment) => payment.uuid === uuid);
        if (!order || !line) {
            return false;
        }
        let data;
        try {
            data = await this.env.services.orm.silent.call(
                "pos.payment.method",
                "btcpay_create_crypto_invoice",
                [{ pm_id: line.payment_method_id.id, amount: line.amount, order_id: order.uuid }]
            );
        } catch (error) {
            this._showError(_t("Unable to create the BTCPay invoice."));
            return false;
        }
        if (data.code !== "0") {
            this._showError(_t("BTCPay invoice creation failed (code %s).", data.code));
            return false;
        }
        const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
        const qrCodeSvg = new XMLSerializer().serializeToString(
            codeWriter.write(data.cryptopay_payment_link, 150, 150)
        );
        line.is_crypto_payment = true;
        line.cryptopay_payment_link = data.cryptopay_payment_link;
        line.cryptopay_payment_link_qr_code =
            "data:image/svg+xml;base64," + window.btoa(qrCodeSvg);
        line.cryptopay_invoice_id = data.invoice_id;
        line.invoiced_crypto_amount = data.crypto_amt;
        line.cryptopay_payment_type = data.cryptopay_payment_type;
        line.conversion_rate = (line.amount / (line.invoiced_crypto_amount / 100000000)).toFixed(2);
        line.setPaymentStatus("waitingCard");
        return this._checkPaymentStatus(line, order.uuid);
    }

    async sendPaymentCancel(order, uuid) {
        await super.sendPaymentCancel(...arguments);
        return true;
    }

    async _checkPaymentStatus(line, orderId) {
        for (let attempt = 0; attempt < POLL_ATTEMPTS; attempt++) {
            line.crypto_payment_status = _t(
                "Checking invoice status %(attempt)s/%(total)s",
                { attempt: attempt + 1, total: POLL_ATTEMPTS }
            );
            let response;
            try {
                response = await this.env.services.orm.silent.call(
                    "pos.payment.method",
                    "btcpay_check_payment_status",
                    [{
                        invoice_id: line.cryptopay_invoice_id,
                        pm_id: line.payment_method_id.id,
                        order_id: orderId,
                    }]
                );
            } catch (error) {
                return false;
            }
            if (["Paid", "Settled"].includes(response.status)) {
                line.crypto_payment_status = _t("Invoice Paid");
                return true;
            }
            if (["Expired", "Invalid"].includes(response.status)) {
                line.crypto_payment_status = _t("Invoice Expired");
                this._showError(_t("The BTCPay invoice has expired."));
                return false;
            }
            await new Promise((resolve) => setTimeout(resolve, POLL_DELAY_MS));
        }
        return false;
    }

    _showError(body) {
        this.env.services.dialog.add(AlertDialog, {
            title: _t("Cryptocurrency Payment"),
            body,
        });
    }
}

register_payment_method("btcpay", PaymentBTCPay);

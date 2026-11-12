/** @odoo-module */

import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

const POLL_ATTEMPTS = 100;
const POLL_DELAY_MS = 50000;

export class PaymentNowPayments extends PaymentInterface {
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
                "create_crypto_invoice",
                [{ pm_id: line.payment_method_id.id, amount: line.amount, order_id: order.uuid }]
            );
        } catch (error) {
            this._showError(_t("Unable to create the NOWPayments invoice."));
            return false;
        }
        if (data.code !== "0") {
            this._showError(_t("NOWPayments invoice creation failed (code %s).", data.code));
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
        line.conversion_rate = data.conversion_rate;
        line.invoiced_crypto_amount = data.crypto_amt;
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
                    "now_check_payment_status",
                    [{
                        invoice_id: line.cryptopay_invoice_id,
                        pm_id: line.payment_method_id.id,
                        order_id: orderId,
                    }]
                );
            } catch (error) {
                return false;
            }
            if (response.payment_status === "finished") {
                line.crypto_payment_status = _t("Invoice Paid");
                line.invoiced_crypto_amount = response.pay_amount;
                line.conversion_rate = (line.amount / line.invoiced_crypto_amount).toFixed(2);
                line.cryptopay_payment_type = response.pay_currency;
                return true;
            }
            if (["expired", "failed", "refunded"].includes(response.payment_status)) {
                this._showError(
                    _t("The NOWPayments invoice ended with status %s.", response.payment_status)
                );
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

register_payment_method("now", PaymentNowPayments);

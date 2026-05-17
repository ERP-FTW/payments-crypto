/** @odoo-module **/

import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";

const BREEZ_PAID_STATUSES = ["paid", "settled", "complete", "succeeded", "success"];
const BREEZ_FAILED_STATUSES = ["expired", "invalid", "failed", "error"];

export class PaymentBreezPayment extends PaymentInterface {
    async send_payment_request(uuid) {
        const order = this.pos.get_order();
        const line =
            order?.payment_ids?.find((paymentLine) => paymentLine.uuid === uuid) ||
            order?.get_selected_paymentline?.();

        if (!order || !line) {
            console.error("Breez: no order or payment line found", { order, uuid });
            return false;
        }

        await super.send_payment_request(...arguments);

        /*
         * If this payment line already has a Breez invoice, do not create
         * another one. Just continue polling the existing invoice.
         */
        if (line.cryptopay_invoice_id && line.cryptopay_payment_link) {
            line.update?.({ crypto_payment_status: "Waiting for Lightning payment" });
            line.crypto_payment_status = "Waiting for Lightning payment";
            line.set_payment_status("cryptowaiting");
            return await this._poll_payment_status(order, line);
        }

        line.set_payment_status("cryptowaiting");
        line.update?.({ crypto_payment_status: "Creating Breez invoice" });
        line.crypto_payment_status = "Creating Breez invoice";

        let data;
        try {
            data = await this.pos.data.call("pos.payment.method", "breez_create_crypto_invoice", [
                {
                    pm_id: line.payment_method_id.id,
                    amount: line.amount,
                    order_id: order.uuid || order.name,
                },
            ]);
        } catch (error) {
            console.error("Breez invoice creation RPC failed", error);
            line.update?.({ crypto_payment_status: "Invoice creation failed" });
            line.crypto_payment_status = "Invoice creation failed";
            line.set_payment_status("retry");
            return false;
        }

        if (!data || String(data.code) !== "0") {
            console.error("Breez invoice creation failed", data);
            line.update?.({
                crypto_payment_status: `Invoice creation failed: ${data?.code || "unknown error"}`,
            });
            line.crypto_payment_status = `Invoice creation failed: ${data?.code || "unknown error"}`;
            line.set_payment_status("retry");
            return false;
        }

        const updates = {
            is_crypto_payment: true,
            cryptopay_payment_link: data.cryptopay_payment_link,
            cryptopay_invoice_id: data.invoice_id,
            invoiced_crypto_amount: data.crypto_amt,
            cryptopay_payment_type: data.cryptopay_payment_type,
            crypto_payment_status: "Invoice created. Waiting for Lightning payment",
        };

        const sats = Number(data.crypto_amt || 0);
        if (sats) {
            updates.conversion_rate = Number(line.amount / (sats / 100000000)).toFixed(2);
        }

        if (data.cryptopay_payment_link && window.ZXing?.BrowserQRCodeSvgWriter) {
            const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
            const qrCodeSvg = new XMLSerializer().serializeToString(
                codeWriter.write(data.cryptopay_payment_link, 150, 150)
            );
            updates.cryptopay_payment_link_qr_code = `data:image/svg+xml;base64,${window.btoa(qrCodeSvg)}`;
        } else {
            console.warn("Breez: ZXing QR writer unavailable; QR image was not generated");
        }

        line.update?.(updates);
        Object.assign(line, updates);
        line.set_payment_status("cryptowaiting");

        /*
         * Critical:
         * Do NOT return true here.
         * Returning true tells POS the terminal payment is complete and causes
         * immediate order validation/sync.
         *
         * Match NOWPayments/BTCPay architecture: invoice creation is only step 1.
         * The terminal request resolves true only after the invoice is actually paid.
         */
        return await this._poll_payment_status(order, line);
    }

    async _poll_payment_status(order, line) {
        for (let attempt = 1; attempt <= 100; attempt++) {
            line.update?.({
                crypto_payment_status: `Checking Breez invoice status ${attempt}/100`,
            });
            line.crypto_payment_status = `Checking Breez invoice status ${attempt}/100`;
            line.set_payment_status("cryptowaiting");

            let apiResp;
            try {
                apiResp = await this.pos.data.call("pos.payment.method", "breez_check_payment_status", [
                    {
                        invoice_id: line.cryptopay_invoice_id,
                        pm_id: line.payment_method_id.id,
                        order_id: order.uuid || order.name,
                    },
                ]);
            } catch (error) {
                console.error("Breez status check failed", error);
                line.update?.({ crypto_payment_status: "Status check failed" });
                line.crypto_payment_status = "Status check failed";
                line.set_payment_status("retry");
                return false;
            }

            const status = String(apiResp?.status || "").toLowerCase();
            const isPaid = String(apiResp?.code) === "0" && BREEZ_PAID_STATUSES.includes(status);

            if (isPaid) {
                line.update?.({ crypto_payment_status: "Invoice paid" });
                line.crypto_payment_status = "Invoice paid";
                line.set_payment_status("done");
                return true;
            }

            if (BREEZ_FAILED_STATUSES.includes(status)) {
                line.update?.({ crypto_payment_status: `Invoice ${status}` });
                line.crypto_payment_status = `Invoice ${status}`;
                line.set_payment_status("retry");
                return false;
            }

            /*
             * Pending/unknown/not_found should keep waiting.
             * Do not return true for any non-paid status.
             */
            line.update?.({
                crypto_payment_status: `Waiting for Lightning payment: ${status || "unknown"} (${attempt}/100)`,
            });
            line.crypto_payment_status = `Waiting for Lightning payment: ${status || "unknown"} (${attempt}/100)`;
            line.set_payment_status("cryptowaiting");

            await new Promise((resolve) => setTimeout(resolve, 5000));
        }

        line.update?.({ crypto_payment_status: "Invoice not confirmed" });
        line.crypto_payment_status = "Invoice not confirmed";
        line.set_payment_status("retry");
        return false;
    }

    async send_payment_cancel(order, uuid) {
        const paymentLine = order?.payment_ids?.find((line) => line.uuid === uuid);
        if (paymentLine) {
            paymentLine.update?.({ crypto_payment_status: "Invoice cancelled" });
            paymentLine.crypto_payment_status = "Invoice cancelled";
            paymentLine.set_payment_status("retry");
        }
        return true;
    }
}
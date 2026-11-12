/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.is_crypto_payment = vals.is_crypto_payment || false;
        this.cryptopay_invoice_id = vals.cryptopay_invoice_id || false;
        this.cryptopay_payment_link = vals.cryptopay_payment_link || false;
        this.cryptopay_payment_type = vals.cryptopay_payment_type || false;
        this.conversion_rate = vals.conversion_rate || 0;
        this.invoiced_crypto_amount = vals.invoiced_crypto_amount || 0;
        this.crypto_payment_status = vals.crypto_payment_status || false;
        this.cryptopay_payment_link_qr_code = false;
        if (this.cryptopay_payment_link && window.ZXing?.BrowserQRCodeSvgWriter) {
            const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
            const qrCodeSvg = new XMLSerializer().serializeToString(
                codeWriter.write(this.cryptopay_payment_link, 150, 150)
            );
            this.cryptopay_payment_link_qr_code =
                "data:image/svg+xml;base64," + window.btoa(qrCodeSvg);
        }
    },
});

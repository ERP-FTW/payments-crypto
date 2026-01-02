odoo.define('mlr_pos_cryptopayment.models', function (require) { // super point of sale models
"use strict";


    var models = require('point_of_sale.models');
    var { Order, Payment } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');

    const PosCryptoPayment = (Payment) => class PosCryptoPayment extends Payment {
        
        constructor(obj, options) {
            super(...arguments);
        }
        //@override
        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);
            json.is_crypto_payment = this.is_crypto_payment;
            json.cryptopay_payment_type = this.cryptopay_payment_type;
            json.cryptopay_invoice_id = this.cryptopay_invoice_id;
            json.cryptopay_payment_link_qr_code = this.cryptopay_payment_link_qr_code;
            json.cryptopay_payment_link = this.cryptopay_payment_link;
            json.invoiced_crypto_amount = this.invoiced_crypto_amount;
            json.conversion_rate = this.conversion_rate;
            return json;
        }
        //@override
        init_from_JSON(json) {
            super.init_from_JSON(...arguments);
            try {
                this.is_crypto_payment = json.is_crypto_payment;
                this.cryptopay_invoice_id = json.cryptopay_invoice_id;
                this.cryptopay_payment_link = json.cryptopay_payment_link;
                this.cryptopay_payment_type = json.cryptopay_payment_type;
                this.conversion_rate = json.conversion_rate;
                const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
                let qr_code_svg = new XMLSerializer().serializeToString(codeWriter.write(json.cryptopay_payment_link, 150, 150));
                this.cryptopay_payment_link_qr_code = "data:image/svg+xml;base64,"+ window.btoa(qr_code_svg);
                this.invoiced_crypto_amount = json.invoiced_crypto_amount;
                }

            catch (error) {
                 console.log(error);
                 return false;
                }
            }
        }
    Registries.Model.extend(Payment, PosCryptoPayment);

});

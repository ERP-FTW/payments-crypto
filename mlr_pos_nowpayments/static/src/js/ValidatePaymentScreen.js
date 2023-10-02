odoo.define("point_of_sale.NowValidatePaymentScreen", function (require) {
    "use strict";
    const PaymentScreen = require("point_of_sale.PaymentScreen");
    const Registries = require("point_of_sale.Registries");
    var rpc = require('web.rpc');
  
    const NowValidatePaymentScreen = (PaymentScreen) =>
      class extends PaymentScreen {
        setup() {
          super.setup();
        }
        async validateOrder(isForceValidate) {
            for (let line of this.paymentLines) {
            console.log("called now validation");
            if(line.is_crypto_payment && line.payment_method.use_payment_terminal == 'now') {
            try {
                let order_id = this.env.pos.get_order().uid;
                let api_resp = await rpc.query({
                    model: 'pos.payment.method',
                    method: 'now_check_payment_status',
                    args: [{ invoice_id: line.cryptopay_invoice_id, pm_id: line.payment_method.id, order_id: order_id }],
                }, {
                    silent: true,
                });
                console.log(api_resp);
                console.log(api_resp.payment_status);

                if (api_resp.payment_status == 'waiting') {
                     console.log("valid now transaction");
                     line.invoiced_crypto_amount = api_resp.pay_amount;
                     line.cryptopay_payment_type = api_resp.pay_currency;
                     let conversion_rate = line.amount/line.invoiced_crypto_amount;
                     line.conversion_rate = conversion_rate.toFixed(2);
                     line.crypto_payment_status = 'Invoice Paid';
                     line.set_payment_status('done');
				}
                                else if (api_resp.payment_status == 'new') {
	                                this.showPopup("ErrorPopup", {
       		                                 title: this.env._t("Payment Request Pending"),
               		                         body: this.env._t("Payment Pending, retry after customer confirms"),
                       		        });
                                }

                                else if (api_resp.payment_status == 'found') {
	                                this.showPopup("ErrorPopup", {
       		                                 title: this.env._t("Payment Request Pending"),
               		                         body: this.env._t("Payment Pending, retry after customer confirms"),
                       		        });
                                }

                                else if (api_resp.payment_status == 'not_found') {
	                                this.showPopup("ErrorPopup", {
       		                                 title: this.env._t("Payment Request Pending"),
               		                         body: this.env._t("Payment Pending, retry after customer confirms"),
                       		        });
                                }


				else if (api_resp.payment_status == 'expired') {
						console.log("expired now transaction");
				        this.showPopup("ErrorPopup", {
                                                 title: this.env._t("Payment Request Expired"),
                                                 body: this.env._t("Payment Request expired, retry to send another send request"),
                                        });
				}}
				catch (error) {
                 console.log(error);
                 return false;
             }}
            }
          super.validateOrder(isForceValidate);
        }
      };
    // CustomValidatePaymentScreen.template = "point_of_sale.CustomValidatePaymentScreenTemplate";
  
    Registries.Component.extend(PaymentScreen, NowValidatePaymentScreen);
  
    return NowValidatePaymentScreen;
  });
  

/** @odoo-module */

import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import { PaymentPhoenixd } from "@mlr_pos_phoenixd/js/payment_phoenixd";

register_payment_method("phoenixd", PaymentPhoenixd);

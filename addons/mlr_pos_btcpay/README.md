# mlr_pos_btcpay — BTCPay Server payment terminal for POS (status on 18.0)

Installs on Odoo 18.0 (`70bdd4035000c836f9f459345e45cc4d408c68d8`, verified together with
`mlr_pos_cryptopayments` and `pos_restaurant`, which `mlr_pos_cryptopayments` depends on). **No
POS session, BTCPay call or browser run has been qualified on 18**, so it is not yet offered as a
ready recipe.

Module root: `addons/mlr_pos_btcpay/mlr_pos_btcpay/`.

## Configuration (POS → Configuration → Payment Methods)

Use a Payment Terminal = BTCPay, then:

| Field | Meaning |
| --- | --- |
| Server URL, API Key | BTCPay Server base URL and a Greenfield API key (`Authorization: token <key>`) with store invoice and rate permissions. |
| BTCPay Store ID | the store that issues invoices. |
| BTCPay Payment Flow | `payment link` (hosted checkout, on-chain or Lightning per store settings) or `direct invoice` (a BOLT11 Lightning invoice paid from the buyer's wallet). |
| Expiration Minutes | invoice lifetime in minutes. |
| Speed Policy | confirmations required on-chain (payment link only). |
| Order minimum / maximum fiat amount | **set the maximum**: it defaults to 0.0 and every amount above it is refused. |

## Provider contract (BTCPay Greenfield API, verified from its OpenAPI definition at btcpayserver `a1d509d`)

- Store invoice `POST /api/v1/stores/{storeId}/invoices`: `amount` (decimal string) and `currency`;
  `checkout.expirationMinutes` is **minutes**; `checkout.speedPolicy` ∈ HighSpeed (0 conf),
  MediumSpeed (1), LowMediumSpeed (2), LowSpeed (6). Status `New`, `Processing` (paid, not
  confirmed), `Expired`, `Invalid`, `Settled`, with `additionalStatus` `PaidLate`, `PaidPartial`,
  `PaidOver`, `Marked`, `Invalid`, `None`.
- Lightning invoice `POST /api/v1/stores/{storeId}/lightning/BTC/invoices`: `amount` in
  **millisatoshi (string)**, `expiry` in **seconds**; status `Unpaid`, `Paid`, `Expired`.
- Rates `GET /api/v1/stores/{storeId}/rates?currencyPair=BTC_USD`: an array of
  `{currencyPair, rate (decimal string), errors}`.
- Webhooks sign the raw body: `BTCPay-Sig: sha256=HMAC256(secret, body)`.

## Known defects at this branch (fix before qualifying)

1. `call_btcpay_api` logs the header dictionary, including `Authorization: Token <api key>`, at INFO.
2. The payment-link path sends `btcpay_expiration_minutes * 60` as `checkout.expirationMinutes`
   (minutes × 60); the Lightning path's `* 60` into `expiry` (seconds) is correct.
3. `action_get_conversion_rate` takes the first rate the store returns without asking for or
   checking a currency pair.
4. A failed direct-invoice status call executes `return false` (NameError).
5. The POS screen code imports `ErrorPopup` from `@web/core/confirmation_dialog/confirmation_dialog`
   and calls `this.popup.add`, neither of which exists in Odoo 18; its error and pending paths fail
   in the browser. Statuses `Paid` (legacy) and `Settled` are treated as paid; `Processing` as pending.
6. The invoice is priced in BTC converted by Odoo from the store's rate; BTCPay can price in the POS
   currency directly (`currency` = POS currency), which removes items 3 and the rounding of
   `get_amount_sats`.

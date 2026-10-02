# mlr_ecommerce_nowpayments — NOWPayments checkout for Odoo 18

Adds NOWPayments (`payment.provider` code `now`) to the Odoo 18 web shop and invoice portal. The
buyer is redirected to a NOWPayments hosted invoice, pays in the coin of their choice, and the Odoo
transaction is confirmed from the state NOWPayments itself reports.

Module root: `addons/mlr_ecommerce_nowpayments/mlr_ecommerce_nowpayments/` (note the nesting: the
addons path needs `addons/mlr_ecommerce_nowpayments` and `addons/mlr_ecommerce_cryptopayments`).
Depends on `website`, `mlr_ecommerce_cryptopayments` (and through it `website_sale`).

Verified on Odoo 18.0 Community (`70bdd4035000c836f9f459345e45cc4d408c68d8`): install, upgrade
from `fbac1cc`, the module tests, and a lab run through the live routes against a local stand-in
for the NOWPayments API. **No call to NOWPayments itself has been made from this branch**: the
provider-side contract below is taken from NOWPayments' documentation and must be confirmed with a
sandbox payment before go-live (see *Before go-live*).

## How a payment completes

1. Checkout renders a form that posts only the transaction reference to
   `POST /payment/now/createInvoice`.
2. That route reads the transaction and opens one NOWPayments invoice (`POST /v1/invoice`) with the
   transaction's own amount and currency, `order_id` = Odoo reference, and three URLs:
   `ipn_callback_url` = `<base>/payment/now/ipn`, `success_url` and `cancel_url` =
   `<base>/payment/now/return?ref=<reference>`. The invoice id and URL are stored on the
   transaction (`crypto_invoice_id`, `crypto_payment_link`); a resubmitted checkout reuses them.
3. The buyer pays on NOWPayments. Odoo learns the outcome by any of three paths, all of which
   re-read the payment from NOWPayments with the transaction's own provider credentials and apply
   the same checks:
   - **IPN** (`POST /payment/now/ipn`): the `x-nowpayments-sig` header must be the HMAC-SHA512 of
     the key-sorted JSON body with the provider's IPN secret. The body only names the payment;
     its state is fetched with `GET /v1/payment/{payment_id}`.
   - **Return page** (`/payment/now/return`): when the buyer comes back.
   - **Reconciliation job** (*NOWPayments: reconcile open transactions*, every 15 minutes): for
     draft/pending NOWPayments transactions up to 8 days old, lists the payments of the
     transaction's own invoice (`GET /v1/payment/?invoiceId=…`, needs the dashboard login) and
     settles from the best one.
4. A fetched payment is applied only if its `order_id` is the transaction reference and its
   `invoice_id` is the transaction's invoice. Then:

   | NOWPayments `payment_status` | Odoo transaction |
   | --- | --- |
   | `finished` and `price_amount`/`price_currency` equal the transaction | `done` |
   | `finished` with a different price amount or currency | `error` ("amount mismatch"), order not confirmed |
   | `waiting`, `confirming`, `confirmed`, `sending` | `pending` |
   | `partially_paid` | `error` with the paid and due amounts; resolve with the buyer |
   | `failed`, `expired`, `refunded` | `cancel` (a `done` transaction is never cancelled) |

   `provider_reference` stores the NOWPayments `payment_id`; `crypto_payment_type`,
   `crypto_invoiced_crypto_amount` and `crypto_conversion_rate` store the coin, coin amount and
   implied rate.
5. Odoo's standard post-processing (`payment` / `account_payment` / `sale`) then confirms the order
   and creates exactly one `account.payment` per transaction. Duplicate or replayed notifications
   are harmless: the state machine ignores a repeated `done`, and a payment is created only when
   the transaction has none.

## Configuration

Website → Configuration → Payment Providers → the NOWPayments record (or Invoicing → Configuration →
Payment Providers):

| Field | Value | Who sets it |
| --- | --- | --- |
| Crypto Payment Provider | ticked | configuration package |
| Server URL | `https://api-sandbox.nowpayments.io` (sandbox) or `https://api.nowpayments.io` | configuration package — this is the environment selection |
| Provider minimum / maximum Fiat Amount | the accepted range, in the transaction currency | configuration package |
| State | Test Mode (sandbox) or Enabled (production); Published for the shop | configuration package |
| API Key | from NOWPayments → Store Settings → API keys | authorized operator, from the credential reference |
| NowPayments Username / Password | dashboard e-mail and password; only used to list payments for reconciliation | authorized operator (password is system-only) |
| NowPayments IPN Secret Key | from NOWPayments → Store Settings → IPN; shown once | authorized operator (system-only) |
| Journal (Configuration tab) | the bank journal that receives the payments | configuration package or BSA decision |

The provider record ships with the module as `mlr_ecommerce_nowpayments.payment_provider_now`
(`noupdate`): a configuration package updates that record instead of creating one, and a module
upgrade does not reset what the client set.

**Connect Now Server** checks the API key with `GET /v1/currencies` (an endpoint that requires it).
It proves the key is accepted, not that a payment works.

### Callback reachability

NOWPayments must be able to `POST` to `<web.base.url>/payment/now/ipn` from the internet. Check
`web.base.url` (or the website domain) is the public HTTPS URL. If IPN cannot reach Odoo,
payments still complete through the return page and the reconciliation job (needs the dashboard
login), only later.

## Before go-live (external acceptance)

Run in the NOWPayments sandbox account named by the task's credential references, from a database
whose public URL NOWPayments can reach:

1. Pay one checkout to `finished`. Expect: the transaction `done` with `provider_reference` equal to
   the NOWPayments payment id shown in the dashboard, the order confirmed, one `account.payment`.
   Record both sides (Odoo records and the dashboard payment).
2. Close the browser after paying. Expect the same result from IPN, or within 15 minutes from the
   reconciliation job.
3. Let one invoice expire. Expect the transaction cancelled and the order unconfirmed.
4. Confirm from a real IPN that the signature check accepts it (the HMAC procedure is reproduced
   from NOWPayments' reference code; a refusal shows as *refused (signature)* in the log).
5. Confirm `GET /v1/payment/?invoiceId=…` filters by invoice on the account (if the account ignores
   the filter, Odoo still matches locally by invoice and order id, but only within the newest 500
   payments of the window).

Sandbox results are simulated by NOWPayments; repeat step 1 with a small real payment in production
before announcing the flow.

## Logging

Logs carry the HTTP method, endpoint and status of each call, and the order id, payment id and
status of each notification. Headers, the API key, the dashboard credentials, the JWT and the IPN
secret are never logged (covered by a test).

## Not provided

- Refunds are not implemented through Odoo (the payment method declares `support_refund` but no
  refund request is sent); refund in NOWPayments and record it in accounting.
- An overpaid or repeated payment on an already confirmed order is logged and ignored, not
  refunded.
- Holding or valuing the received coin is a separate decision (`account_cryptocurrency`); a
  merchant whose NOWPayments account converts to fiat needs neither.

## Developer notes

- Provider API calls: `payment.provider._nowpayments_make_request()` (transaction's provider only).
- Invoice: `payment.transaction._nowpayments_get_invoice_url()`.
- Verified state: `_process_notification_data()` → `_nowpayments_apply_verified_payment()`.
- Reconciliation: `_nowpayments_reconcile()`, `_cron_nowpayments_reconcile()`.
- Signature: `controllers/main.py` `nowpayments_signed_message()` reproduces JavaScript's
  `JSON.stringify` of the recursively key-sorted body (numbers such as `100.0` serialize as `100`).
- Tests: `tests/test_nowpayments_flows.py` (HTTP routes with a fake NOWPayments API: trusted amount
  and currency, one invoice per transaction, per-company provider, signature refusal, completion
  without the buyer, amount mismatch, foreign payment, duplicate notifications with real accounting
  post-processing, delayed confirmation, partial payment, beyond-ten-payments return, no secrets in
  logs) and `tests/test_nowpayments_signature.py`. Run with
  `odoo-bin -u mlr_ecommerce_nowpayments --test-tags /mlr_ecommerce_nowpayments`.

# mlr_pos_nowpayments — NOWPayments payment terminal for POS (status on 18.0)

**Not usable on Odoo 18 at this branch.** Installing it on Odoo 18.0
(`70bdd4035000c836f9f459345e45cc4d408c68d8`) fails while loading
`views/pos_payment_method.xml`: *"Since 17.0, the "attrs" and "states" attributes are no longer
used."* Beyond the view, the module is still Odoo 16 code: its manifest declares version `16.0`
and loads assets into `point_of_sale.assets`, and its JavaScript uses the pre-17 `odoo.define`,
`point_of_sale.Registries` and `web.rpc` APIs, which Odoo 18's POS no longer provides.

## Port to use

An Odoo 18 port exists outside this branch, in ERP-FTW/odoo pull request #53
(`codex/update-pos-nowpayments-integration-for-odoo-18`, head `2bf18ea4`): views without `attrs`,
assets in `point_of_sale._assets_pos`, an ES-module `PaymentInterface`, an OWL `PaymentScreen`
patch, no credential logging, request timeouts, and the `return false` fix. It applies cleanly to
this layout:

```bash
git -C <ERP-FTW/odoo clone> diff ddcd614 2bf18ea --relative=payments-crypto-18.0/ \
  | git apply --directory=addons
```

payments-crypto #5 (missing auth-token guard) applies on top of it. Port it as its own reviewed
change, then qualify it in a POS browser run before offering it to a client.

## What the 18.0 code does (for that port)

- Payment link: `POST /v1/invoice` with the order uid as `order_id`; status by listing the newest
  ten payments with a JWT and matching `order_id` (same ten-payment limit the ecommerce module had).
- Direct invoice: `POST /v1/payment` for a selected coin, status by `GET /v1/payment/{id}`.
- `now_sandbox` / `now_sandbox_case` put calls in NOWPayments' sandbox case mode: simulated, never
  provider evidence.
- Defects to carry into the port: the header dictionary (with `x-api-key` and the Bearer token) and
  the `/v1/auth` payload (dashboard e-mail and password) are logged at INFO; `return false`
  (NameError) on a failed direct-invoice status call; the price currency is always the main
  company's, not the POS's.

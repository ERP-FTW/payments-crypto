# Target model map

| Legacy concept | Replacement | Notes |
| --- | --- | --- |
| `account_cryptocurrency` | `account_crypto` | Rewrite as the accounting engine, not a compatibility rename. |
| `res.currency.move` | `crypto.asset.move` | New model for crypto subledger movements; no legacy alias. |
| `res.currency.move.line` | `crypto.asset.move.line` | New model for wallet/lot movement lines; no legacy alias. |
| Currency inventoried flag on `res.currency` | `crypto.asset` | Crypto identity belongs to network+asset, not fiat currency master data. |
| Currency FIFO remaining Float quantity | `crypto.asset.lot.remaining_atomic_units` | Exact atomic integer string / numeric-backed reporting. |
| `mlr_pos_cryptopayments` | `pos_crypto` | Provider-neutral POS integration only. |
| `mlr_pos_phoenixd` | `crypto_provider_phoenixd` + `pos_crypto_phoenixd` | API client separated from POS adapter. |
| `mlr_pos_btcpay` | `crypto_provider_btcpay` + `pos_crypto_btcpay` | API client separated from POS adapter. |
| `mlr_pos_breez_greenlight` | `crypto_provider_breez` + `pos_crypto_breez` | No mnemonic/seed storage in business models. |
| `mlr_pos_nowpayments` | `crypto_provider_nowpayments` + `pos_crypto_nowpayments` | Normalize provider events and settlements. |
| `mlr_ecommerce_cryptopayments` | `payment_crypto` | Provider-neutral payment integration. |
| `mlr_ecommerce_nowpayments` | `crypto_provider_nowpayments` + `payment_crypto_nowpayments` | Webhook/controller normalizes events; accounting remains in `account_crypto`. |

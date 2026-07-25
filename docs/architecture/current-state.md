# Current-state architecture audit

## Repository shape

The repository contains active addon copies under `addons/` and duplicate module trees at the repository root for several `mlr_*` modules. The duplicate root copies should be removed when the canonical `/addons` replacements exist.

## Current module classification

| Current module | Classification | Findings | Target |
| --- | --- | --- | --- |
| `addons/account_cryptocurrency` | Rewrite | Defines `res.currency.move` and `res.currency.move.line`, extends `res.currency`, `account.payment`, and creates accounting from currency inventory moves using Float quantities and Date-based flows. | `account_crypto` with `crypto.asset.move`, lots, disposals, exact atomic quantities, snapshots, and settlement-driven posting. |
| `addons/currency_valuation_reporting` | Rewrite | Depends on `account_cryptocurrency` and reports on obsolete currency inventory models. | `account_crypto_reporting`. |
| `addons/mlr_pos_cryptopayments` | Split | POS payment fields combine API settings, fiat/crypto rates, QR payloads, provider IDs, and sats on `pos.payment`/`pos.payment.method`; uses Float for rates and crypto amounts. | `pos_crypto` plus provider core modules and POS adapters. |
| `addons/mlr_pos_phoenixd` | Split | POS terminal adapter includes Phoenixd API client and credentials on POS payment method. | `crypto_provider_phoenixd` and `pos_crypto_phoenixd`. |
| `addons/mlr_pos_btcpay` | Split | POS terminal adapter includes BTCPay API calls and invoice polling. | `crypto_provider_btcpay` and `pos_crypto_btcpay`. |
| `addons/mlr_pos_breez_greenlight` | Rewrite | Stores Breez mnemonic/invite/working-directory configuration in POS business models, which violates secret-handling requirements. | `crypto_provider_breez` and `pos_crypto_breez`; no seed phrase or mnemonic storage in business models. |
| `addons/mlr_pos_nowpayments` | Split | POS adapter stores username/password and hard-coded asset selections; duplicate nested copy exists under `mlr_pos_nowpayments2`. | `crypto_provider_nowpayments` and `pos_crypto_nowpayments`. |
| `addons/mlr_ecommerce_cryptopayments` | Split | Extends payment provider/transaction with crypto fields and API key fields; no normalized settlement model. | `payment_crypto` plus provider adapters. |
| `addons/mlr_ecommerce_nowpayments` | Split | Combines eCommerce controller, payment provider settings, API calls, and transaction processing. | `crypto_provider_nowpayments` and `payment_crypto_nowpayments`. |
| Root-level `mlr_*` module copies | Delete | Duplicate technical module names outside `/addons`. | Remove after scaffold replacement. |

## Odoo 18 API observations to preserve

The target design must align with Odoo 18 model boundaries: `res.currency`/`res.currency.rate` serve currency rounding and daily rate lookup; `account.payment` delegates posted accounting to `account.move`; `account.move` and `account.move.line` are the balanced journal-entry source of truth; `payment.provider` and `payment.transaction` manage online payment provider configuration and transaction state; `pos.payment`, `pos.payment.method`, `pos.order`, and POS session closing create standard POS payment/session accounting. Crypto settlement accounting must integrate by linking to these models rather than bypassing their posting semantics.

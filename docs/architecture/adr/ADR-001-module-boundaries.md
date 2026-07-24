# ADR-001: Module boundaries

Status: accepted.

## Decision

Adopt one canonical Odoo addon tree under `addons/` with these greenfield modules:

- `crypto_base`: provider-neutral networks, assets, wallets, exact quantity helpers, immutable rate snapshots, append-only provider events, and settlements. Depends on `base`; may depend on `mail` only if audit chatter is required.
- `account_crypto`: authoritative accounting engine. Depends on `account` and `crypto_base`.
- `account_crypto_reporting`: reporting views over `account_crypto` subledger objects.
- `crypto_provider_phoenixd`, `crypto_provider_btcpay`, `crypto_provider_breez`, `crypto_provider_nowpayments`: provider API clients and normalizers only. They create provider events and settlements; they do not create accounting entries and do not depend on POS, Payment, website, or `account_crypto` unless a later PR documents a concrete technical reason.
- `pos_crypto`: POS integration layer. Depends on `point_of_sale` and `account_crypto`.
- `pos_crypto_phoenixd`, `pos_crypto_btcpay`, `pos_crypto_breez`, `pos_crypto_nowpayments`: POS/provider adapters. Each depends on `pos_crypto` plus its provider core module.
- `payment_crypto`: eCommerce/payment integration layer. Depends on `payment` and `account_crypto`.
- `payment_crypto_btcpay`, `payment_crypto_nowpayments`: payment/provider adapters.
- Localization adapters: optional modules such as `l10n_us_account_crypto`, `l10n_ca_account_crypto`, `l10n_uk_account_crypto`, `l10n_au_account_crypto`, `l10n_de_account_crypto`, and `account_crypto_ifrs` for localized accounts, taxes, disclosures, and reports.

## Rationale

The current repository mixes provider APIs, POS UI, payment-provider extensions, secrets, currency inventory, and accounting. The target split makes settlement evidence provider-neutral and routes all journal entry creation through `account_crypto`.

## Consequences

No compatibility aliases will be created for `res.currency.move`, `res.currency.move.line`, or old `mlr_*` module names. The next PR can establish module namespaces by removing obsolete active modules and scaffolding the accepted names without revisiting boundaries.

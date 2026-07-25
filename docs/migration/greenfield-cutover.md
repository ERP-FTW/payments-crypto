# Greenfield cutover plan

This redesign is greenfield. Obsolete module names, XML IDs, model names, and database migration compatibility are not preserved unless a future prompt explicitly asks for a one-off importer.

## Phase 1 repository reset status

Phase 1 establishes a single canonical addon tree under `addons/` and removes the active legacy module directories. Useful source references remain available in Git history; no archive copy is kept in the working tree because duplicate technical module names would make Odoo addon discovery ambiguous.

## Cutover mapping

- Removed `addons/account_cryptocurrency`; replaced by scaffold `addons/account_crypto`.
- Removed `addons/currency_valuation_reporting`; replaced by scaffold `addons/account_crypto_reporting`.
- Removed `addons/mlr_pos_cryptopayments`; replaced by scaffold `addons/pos_crypto`.
- Removed `addons/mlr_pos_phoenixd`; replaced by scaffolds `addons/crypto_provider_phoenixd` and `addons/pos_crypto_phoenixd`.
- Removed `addons/mlr_pos_btcpay`; replaced by scaffolds `addons/crypto_provider_btcpay` and `addons/pos_crypto_btcpay`.
- Removed `addons/mlr_pos_breez_greenlight`; replaced by scaffolds `addons/crypto_provider_breez` and `addons/pos_crypto_breez`.
- Removed `addons/mlr_pos_nowpayments`; replaced by scaffolds `addons/crypto_provider_nowpayments` and `addons/pos_crypto_nowpayments`.
- Removed `addons/mlr_ecommerce_cryptopayments`; replaced by scaffold `addons/payment_crypto`.
- Removed `addons/mlr_ecommerce_nowpayments`; replaced by scaffolds `addons/crypto_provider_nowpayments` and `addons/payment_crypto_nowpayments`.
- Removed root-level duplicate `mlr_*` module trees so `/addons` is the only canonical active module tree.

No compatibility aliases are added for `res.currency.move`, `res.currency.move.line`, or old `mlr_*` modules.

## Deferred data handling

Existing deployments must export business evidence before uninstalling legacy modules if they need historical reference. A later migration project may build one-off importers into `crypto.settlement`, `crypto.provider.event`, `crypto.rate.snapshot`, and `crypto.asset.lot`; that importer is intentionally outside the greenfield reset.

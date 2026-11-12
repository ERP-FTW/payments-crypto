# Odoo cryptocurrency payment addons

This repository uses the standard Odoo addon layout: each module is a direct child of the repository root. Add the checkout root to `addons_path`; no nested `addons/` directories are required.

## Modules

- `account_cryptocurrency`
- `currency_valuation_reporting`
- `mlr_ecommerce_cryptopayments`
- `mlr_ecommerce_nowpayments`
- `mlr_pos_btcpay`
- `mlr_pos_cryptopayments`
- `mlr_pos_nowpayments`

## Migration branches

`migration/18-to-19` is the agency migration working base. `19.0` is the version branch configured for the CloudPepper test attachment. Both start from the existing 18.0 history; the layout preparation does not certify Odoo 19 compatibility. Manifest/API migrations and module install, upgrade, and functional tests remain part of the migration work.

The `18.0` branch retains its existing layout. Module technical names, XML identifiers, source code, and assets are unchanged by the directory moves.

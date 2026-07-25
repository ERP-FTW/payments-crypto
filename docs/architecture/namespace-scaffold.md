# Greenfield namespace scaffold

Phase 1 creates installable scaffold modules only. These modules intentionally contain no provider client behavior, accounting posting behavior, POS JavaScript behavior, or payment transaction behavior.

## Dependency policy

Provider core modules depend only on `crypto_base`. They do not depend on POS, website, payment, `account`, or `account_crypto`; provider-specific POS and payment adapters compose provider core modules with `pos_crypto` or `payment_crypto`.

`crypto_base` owns the placeholder Crypto menu and security groups required to validate basic XML loading. Later runtime PRs will add model access rules and record rules alongside the actual models.

## Validation scripts

- `scripts/check_odoo_scaffolds.py` performs static manifest, dependency, XML, duplicate-name, obsolete-module, and provider-boundary checks.
- `scripts/odoo_install_chain.sh` is the Odoo-backed clean-database install/uninstall check. It expects `ODOO_BIN`, `ODOO_DATABASE`, and `ODOO_ADDONS_PATH` environment variables where needed.

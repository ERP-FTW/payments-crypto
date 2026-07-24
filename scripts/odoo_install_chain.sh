#!/usr/bin/env bash
set -euo pipefail

: "${ODOO_BIN:=odoo-bin}"
: "${ODOO_DATABASE:=crypto_scaffold_test}"
: "${ODOO_ADDONS_PATH:=addons}"

MODULES=(
  crypto_base
  account_crypto
  account_crypto_reporting
  crypto_provider_phoenixd
  crypto_provider_btcpay
  crypto_provider_breez
  crypto_provider_nowpayments
  pos_crypto
  pos_crypto_phoenixd
  pos_crypto_btcpay
  pos_crypto_breez
  pos_crypto_nowpayments
  payment_crypto
  payment_crypto_btcpay
  payment_crypto_nowpayments
)

"${ODOO_BIN}" \
  --addons-path="${ODOO_ADDONS_PATH}" \
  --database="${ODOO_DATABASE}" \
  --init="$(IFS=,; echo "${MODULES[*]}")" \
  --stop-after-init \
  --without-demo=all

"${ODOO_BIN}" shell \
  --addons-path="${ODOO_ADDONS_PATH}" \
  --database="${ODOO_DATABASE}" <<'PY'
modules = [
    "crypto_base",
    "account_crypto",
    "account_crypto_reporting",
    "crypto_provider_phoenixd",
    "crypto_provider_btcpay",
    "crypto_provider_breez",
    "crypto_provider_nowpayments",
    "pos_crypto",
    "pos_crypto_phoenixd",
    "pos_crypto_btcpay",
    "pos_crypto_breez",
    "pos_crypto_nowpayments",
    "payment_crypto",
    "payment_crypto_btcpay",
    "payment_crypto_nowpayments",
]
env["ir.module.module"].search([("name", "in", modules)]).button_immediate_uninstall()
env.cr.commit()
PY

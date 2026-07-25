#!/usr/bin/env bash
set -euo pipefail

readonly COMPOSE_FILE="compose.test.yaml"
readonly DATABASE="crypto_scaffold_test"
readonly MODULES="crypto_base,account_crypto,account_crypto_reporting,crypto_provider_phoenixd,crypto_provider_btcpay,crypto_provider_breez,crypto_provider_nowpayments,pos_crypto,pos_crypto_phoenixd,pos_crypto_btcpay,pos_crypto_breez,pos_crypto_nowpayments,payment_crypto,payment_crypto_btcpay,payment_crypto_nowpayments"

cleanup() {
  docker compose -f "${COMPOSE_FILE}" down --volumes --remove-orphans
}
trap cleanup EXIT

docker compose -f "${COMPOSE_FILE}" up --detach --wait db
docker compose -f "${COMPOSE_FILE}" run --rm odoo \
  --database="${DATABASE}" \
  --init="${MODULES}" \
  --stop-after-init \
  --without-demo=all

printf '%s\n' \
  "modules = '${MODULES}'.split(',')" \
  "records = env['ir.module.module'].search([('name', 'in', modules)])" \
  "assert set(records.mapped('name')) == set(modules)" \
  "assert set(records.mapped('state')) == {'installed'}" \
  "for name in reversed(modules):" \
  "    env['ir.module.module'].search([('name', '=', name)]).button_immediate_uninstall()" \
  "env.cr.commit()" \
  | docker compose -f "${COMPOSE_FILE}" run --rm --no-TTY odoo odoo shell \
      --database="${DATABASE}" \
      --stop-after-init

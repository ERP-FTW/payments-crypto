"""Preserve legacy transfer routes while introducing network-aware identities."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    currencies = env["res.currency"].search([("inventoried", "=", True), ("crypto_asset_id", "=", False)])
    for currency in currencies:
        asset = env["crypto.asset"].search([("network_code", "=", "legacy-unknown"), ("symbol", "=", currency.name.upper()), ("is_native_asset", "=", True)], limit=1)
        if not asset:
            asset = env["crypto.asset"].create({"name": f"{currency.name} (legacy network unknown)", "symbol": currency.name, "network_code": "legacy-unknown", "is_native_asset": True, "decimal_places": currency.decimal_places or 8, "res_currency_id": currency.id, "notes": "Created during upgrade; select the correct network before live use."})
        currency.crypto_asset_id = asset
    for route in env["crypto.cashout.config"].search([("crypto_asset_id", "=", False)]):
        route.crypto_asset_id = route.crypto_currency_id.crypto_asset_id

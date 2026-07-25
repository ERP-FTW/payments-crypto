#!/usr/bin/env python3
"""Static checks for the greenfield Odoo addon scaffolds."""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

EXPECTED = {
    "crypto_base": ["base"],
    "account_crypto": ["account", "crypto_base"],
    "account_crypto_reporting": ["account_crypto"],
    "crypto_provider_phoenixd": ["crypto_base"],
    "crypto_provider_btcpay": ["crypto_base"],
    "crypto_provider_breez": ["crypto_base"],
    "crypto_provider_nowpayments": ["crypto_base"],
    "pos_crypto": ["point_of_sale", "account_crypto"],
    "pos_crypto_phoenixd": ["pos_crypto", "crypto_provider_phoenixd"],
    "pos_crypto_btcpay": ["pos_crypto", "crypto_provider_btcpay"],
    "pos_crypto_breez": ["pos_crypto", "crypto_provider_breez"],
    "pos_crypto_nowpayments": ["pos_crypto", "crypto_provider_nowpayments"],
    "payment_crypto": ["payment", "account_crypto"],
    "payment_crypto_btcpay": ["payment_crypto", "crypto_provider_btcpay"],
    "payment_crypto_nowpayments": ["payment_crypto", "crypto_provider_nowpayments"],
}
OBSOLETE = {
    "account_cryptocurrency",
    "currency_valuation_reporting",
    "mlr_pos_cryptopayments",
    "mlr_pos_phoenixd",
    "mlr_pos_btcpay",
    "mlr_pos_breez_greenlight",
    "mlr_pos_nowpayments",
    "mlr_ecommerce_cryptopayments",
    "mlr_ecommerce_nowpayments",
}
FORBIDDEN_PROVIDER_DEPS = {"point_of_sale", "website", "website_sale", "payment", "account", "account_crypto"}


def load_manifest(path: Path) -> dict:
    return ast.literal_eval(path.read_text())


def validate_repository(root: Path) -> list[str]:
    """Return actionable scaffold validation failures for ``root``."""
    failures: list[str] = []
    addons = root / "addons"
    manifests = sorted(root.glob("**/__manifest__.py"))
    technical_names = [p.parent.name for p in manifests]
    duplicates = sorted({name for name in technical_names if technical_names.count(name) > 1})
    if duplicates:
        failures.append(f"duplicate technical module names: {', '.join(duplicates)}")

    active = {p.parent.name: p for p in addons.glob("*/__manifest__.py")}
    missing = sorted(set(EXPECTED) - set(active))
    if missing:
        failures.append(f"missing expected addons: {', '.join(missing)}")
    obsolete_active = sorted(set(active) & OBSOLETE)
    if obsolete_active:
        failures.append(f"obsolete addons still active: {', '.join(obsolete_active)}")

    root_obsolete = sorted(
        p.parent.name
        for p in root.glob("*/__manifest__.py")
        if p.parent.name in OBSOLETE
    )
    if root_obsolete:
        failures.append(f"obsolete duplicate root addons still present: {', '.join(root_obsolete)}")

    for module, deps in EXPECTED.items():
        manifest_path = active.get(module)
        if not manifest_path:
            continue
        try:
            manifest = load_manifest(manifest_path)
        except Exception as exc:  # noqa: BLE001 - report all manifest syntax issues.
            failures.append(f"{module}: invalid manifest: {exc}")
            continue
        if manifest.get("depends") != deps:
            failures.append(f"{module}: depends {manifest.get('depends')!r} != {deps!r}")
        if not manifest.get("installable"):
            failures.append(f"{module}: manifest is not installable")
        if "assets" in manifest and not manifest["assets"]:
            failures.append(f"{module}: empty assets key should be omitted")
        for rel in manifest.get("data", []):
            data_path = manifest_path.parent / rel
            if not data_path.exists():
                failures.append(f"{module}: missing data file {rel}")
                continue
            if data_path.suffix == ".xml":
                try:
                    ET.parse(data_path)
                except ET.ParseError as exc:
                    failures.append(f"{module}: XML parse error in {rel}: {exc}")
        if module.startswith("crypto_provider_"):
            bad = sorted(set(manifest.get("depends", [])) & FORBIDDEN_PROVIDER_DEPS)
            if bad:
                failures.append(f"{module}: forbidden provider dependencies: {', '.join(bad)}")

    return failures


def main() -> int:
    failures = validate_repository(Path.cwd())
    if failures:
        print("Scaffold check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Scaffold check passed for {len(EXPECTED)} greenfield addons.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

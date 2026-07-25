import json
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase
from ..models.crypto_ledger import canonical_json, normalize_atomic, payload_digest


class TestCryptoLedger(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.asset = cls.env["crypto.asset"].create({"name": "Bitcoin", "symbol": "btc", "network_code": "bitcoin", "is_native_asset": True, "decimal_places": 8})
        cls.provider = cls.env["crypto.cashout.provider"].create({"name": "Mock", "code": "mock_crypto", "environment": "mock", "mock_ipn_secret": "test-secret"})

    def test_atomic_normalization_and_rejection(self):
        self.assertEqual(normalize_atomic("000200000"), "200000")
        for invalid in ("-1", "1.2", "", " 1x"):
            with self.assertRaises(ValidationError):
                normalize_atomic(invalid)

    def test_asset_network_identity(self):
        with self.assertRaises(ValidationError):
            self.env["crypto.asset"].create({"name": "Duplicate", "symbol": "BTC", "network_code": "BITCOIN", "is_native_asset": True, "decimal_places": 8})

    def test_recursive_canonical_payload_hash(self):
        left = {"z": [{"b": 2, "a": 1}], "a": 0}
        right = {"a": 0, "z": [{"a": 1, "b": 2}]}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(payload_digest(left), payload_digest(right))

    def test_consumed_snapshot_is_immutable(self):
        payload = json.dumps({"quote": "one"})
        snapshot = self.env["crypto.rate.snapshot"].create({"company_id": self.env.company.id, "base_currency_id": self.env.company.currency_id.id, "crypto_asset_id": self.asset.id, "purpose": "checkout", "quoted_at": "2026-01-01 00:00:00", "source": "mock", "source_pair": "BTC/USD", "rate_crypto_per_base": "0.00002", "rate_base_per_crypto": "50000.00", "raw_payload": payload})
        snapshot.write({"state": "consumed"})
        with self.assertRaises(UserError):
            snapshot.write({"rate_base_per_crypto": "51000"})
        with self.assertRaises(UserError):
            snapshot.unlink()

    def test_event_signature_and_duplicate_are_idempotent(self):
        payload = {"event_id": "evt-1", "status": "processing", "id": "object-1", "nested": {"z": 1, "a": 2}}
        signature = self.provider._sign_ipn(payload)
        event, duplicate = self.provider.process_signed_ipn(payload, signature)
        self.assertTrue(event.signature_verified)
        self.assertFalse(duplicate)
        same, duplicate = self.provider.process_signed_ipn(payload, signature)
        self.assertEqual(event, same)
        self.assertTrue(duplicate)
        with self.assertRaises(AccessError):
            event.write({"event_type": "tampered"})
        with self.assertRaises(AccessError):
            event.unlink()

    def test_invalid_signature_has_no_settlement(self):
        payload = {"event_id": "evt-bad", "status": "finished", "id": "bad-object"}
        event, duplicate = self.provider.process_signed_ipn(payload, "invalid")
        self.assertFalse(duplicate)
        self.assertFalse(event.signature_verified)
        self.assertFalse(event.settlement_id)

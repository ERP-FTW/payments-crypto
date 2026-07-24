# ADR-003: Exact quantity representation

Status: accepted.

## Options evaluated

- `fields.Float`: rejected for authoritative crypto atomic units. Odoo float fields are Python floating-point values with precision helpers for rounding and comparison; they are not exact arbitrary-precision ledgers.
- Standard `fields.Integer`: rejected as the universal representation. It is adequate for 2,100,000,000,000,000 satoshis on PostgreSQL `int8`, but it is not future-proof for arbitrary 18-decimal tokens with very large whole-unit supplies and cannot represent exact decimal rates.
- PostgreSQL `numeric` through a reusable custom ORM field or a validated integer-string strategy backed by SQL constraints: accepted for implementation evaluation.

## Decision

Use validated integer strings for atomic quantities in business models in the first implementation, with helper methods converting to `decimal.Decimal` for display and arithmetic and generated/cast SQL reporting views where aggregation is required. Monetary fiat values and rates use exact decimal strings or PostgreSQL `numeric` support once a reusable Odoo field is introduced and proven by tests.

Atomic unit fields must accept only base-10 integer text with optional leading minus where explicitly allowed. They must round-trip values at least as large as `2100000000000000`, support 18-decimal assets by representing one full token as `1000000000000000000` atomic units, and perform addition/subtraction with Python `Decimal` or `int`, never binary float.

## Reporting strategy

Operational tables store exact text. SQL reports cast validated values to `numeric` in views, e.g. `requested_atomic_units::numeric`, after database constraints guarantee the text is numeric. High-volume reports may add generated `numeric` columns in a later PR if Odoo 18 field behavior is validated.

## Required tests

Tests must cover BTC satoshi round-trip, 18-decimal token round-trip, addition/subtraction, values above 32-bit integer range, serialization/deserialization, and zero-residual behavior.

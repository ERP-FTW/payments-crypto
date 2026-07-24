# ADR-005: Accounting timing

Status: accepted.

## POS timing points

- Provider confirmation: best evidence that crypto was received or that a processor accepted liability.
- Order validation: best evidence for sale/tax recognition in POS, but crypto may still be pending or underpaid.
- Invoice posting: authoritative for invoice receivable/revenue/tax, not necessarily for settlement receipt.
- Session close: Odoo POS aggregates and posts session accounting; using it for crypto asset recognition risks mixing settlement evidence with cash-control timing.

## Decision

`account_crypto` posts crypto settlement accounting at settlement confirmation. POS order validation and invoice posting keep standard fiat accounting. Session close remains standard POS accounting and must not independently recognize crypto assets. Double posting is prevented by idempotency keys on `crypto.settlement`, links from settlement to `account.move` and `crypto.asset.move`, and uniqueness constraints for provider events and accounting artifacts.

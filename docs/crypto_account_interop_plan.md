# Interoperability plan: `mlr_ecommerce_cryptopayments`, `mlr_ecommerce_nowpayments` ⇄ `account_cryptocurrency`

## Goals
- Ensure ecommerce crypto payments flow through `account.payment.action_post()` so `account_cryptocurrency` valuation entries remain the single source of truth.
- Preserve traceability across `payment.transaction` → `account.payment` → `res.currency.move` → `account.move`.
- Normalize provider metadata so valuation and reporting do not need to infer provider-specific details.
- Reuse the same accounting technique later for POS (`mlr_pos_*`) by extracting shared helpers/mixins.

## Phase 0 — Discovery and alignment
1. Inventory current hooks in:
   - `account_cryptocurrency` around `account.payment.action_post()`.
   - `mlr_ecommerce_cryptopayments` and `mlr_ecommerce_nowpayments` around transaction completion (`_process_notification_data`, `_set_done`, post-processing hooks).
2. Identify how crypto journals are configured and how the crypto currency is chosen today.
3. Confirm idempotency expectations for provider notifications (same notification can be received multiple times).

Deliverable: short design note and list of impacted models/methods.

## Phase 1 — Canonical entry point via `account.payment`
Treat `account.payment` as the only accounting trigger for ecommerce crypto settlements.

### 1.1 Add a reusable payment creation service
Create a shared helper (in a thin new integration module or a shared mixin) that:
- Accepts a `payment.transaction` and normalized crypto metadata.
- Resolves the crypto currency, amount, journal, partner, and date.
- Creates an `account.payment` in the **crypto currency** with:
  - `payment_type='inbound'`
  - `currency_id=<crypto currency>`
  - `amount=<crypto amount>`
  - `journal_id=<crypto journal for that currency>`
  - `date=<settlement/notification date>`
  - `payment_transaction_id=<transaction>`
- Posts the payment via `action_post()`.

### 1.2 Hook NowPayments completion to the service
In the NowPayments transaction completion path (e.g., right after `_set_done()` in `_process_notification_data`):
1. Normalize provider payload into crypto metadata.
2. Call the shared payment creation service.
3. Ensure the hook is idempotent:
   - If a posted `account.payment` already exists for the transaction, skip creation.

### 1.3 Define journal resolution rules
Add explicit journal lookup rules:
- Prefer a configured crypto journal on the provider/method.
- Fall back to a company-level mapping: crypto currency → crypto journal.
- Fail loudly with a functional error if no journal is available.

Deliverable: ecommerce “done” ⇒ posted `account.payment` in crypto currency.

## Phase 2 — Traceability fields across accounting objects
Introduce explicit linkage fields so auditors can traverse the chain without inference.

### 2.1 Extend `account.payment`
Add:
- `payment_transaction_id = fields.Many2one('payment.transaction', index=True, ondelete='set null')`
- SQL constraint to avoid duplicates per transaction (e.g., unique when state is posted).

### 2.2 Extend `res.currency.move`
Add:
- `payment_transaction_id` (stored related from `account.payment`, or written directly during creation).
- `account_payment_id` if missing or not already present.

### 2.3 Optional: extend `res.currency.move.line`
Add:
- A related `payment_transaction_id` for easier reporting domains.

Deliverable: consistent links across all valuation artifacts.

## Phase 3 — Provider metadata normalization
Standardize provider metadata so accounting/reporting modules can be provider-agnostic.

### 3.1 Normalize on `payment.transaction`
Add crypto-focused fields:
- `crypto_currency_id`
- `crypto_amount`
- `crypto_rate` (crypto → company currency, at settlement time)
- `provider_invoice_id`
- `provider_payout_id`
- Optional: `provider_payload_json` (sanitized snapshot for audits/debugging)

### 3.2 Copy metadata onto accounting records
When creating the `account.payment`, copy (or relate) relevant fields:
- On `account.payment`: `crypto_currency_id`, `crypto_amount`, `crypto_rate`, `provider_invoice_id`, `provider_payout_id`.
- On `res.currency.move`: copy or relate the same fields if reporting commonly starts from valuation entries.

### 3.3 Rate policy alignment
Explicitly define which rate is authoritative for valuation:
- Prefer provider-settlement rate when available.
- Fall back to Odoo FX rates only when the provider does not supply one.
- Record both “provider rate” and “system rate” if needed for reconciliation diagnostics.

Deliverable: valuation/reporting modules can rely on normalized fields without provider-specific parsing.

## Phase 4 — Idempotency, reconciliation, and safety rails
1. Idempotency:
   - Add a transaction-level guard like `account_payment_id` and/or a search domain on `payment_transaction_id` + state.
2. Amount mismatch handling:
   - If provider-reported crypto amount differs from expected amount beyond tolerance, post but flag for review.
3. Reconciliation:
   - Ensure the posted `account.payment` is linked to the originating invoice/order so standard reconciliation flows work.
4. Operational visibility:
   - Add smart buttons from `payment.transaction` to the created `account.payment` and to resulting valuation moves.

Deliverable: robust production behavior under retries and edge cases.

## Phase 5 — Prepare for POS reuse
Design the ecommerce implementation so POS can adopt it with minimal change.

### 5.1 Extract shared primitives
Move shared logic into reusable helpers/mixins:
- `normalize_provider_crypto_payload(transaction, payload) -> crypto metadata`
- `create_and_post_crypto_payment(transaction, metadata)`
- `resolve_crypto_journal(company, crypto_currency, provider=None)`

### 5.2 POS adoption path
For POS modules:
- Call the same `create_and_post_crypto_payment(...)` helper at the “payment confirmed/done” point.
- Reuse the same metadata fields and linkage fields, so reports work across ecommerce and POS.

Deliverable: one accounting pattern, two channels (ecommerce now, POS later).

## Suggested milestones and sequencing
1. Phase 1 (canonical payment posting) — highest value, unblocks valuation correctness.
2. Phase 2 (traceability fields) — required for auditability and clean linking.
3. Phase 3 (metadata normalization) — required for provider-agnostic reporting.
4. Phase 4 (idempotency and safety rails) — harden for production.
5. Phase 5 (POS reuse extraction) — refactor after correctness is proven.

## Acceptance criteria
- When a NowPayments transaction transitions to `done`, exactly one posted `account.payment` exists and it is in the crypto currency.
- Posting that payment creates the expected valuation entries through `account_cryptocurrency`.
- From any valuation move, a user can navigate back to the originating `payment.transaction`.
- Reporting can group/filter by `crypto_currency_id`, `crypto_amount`, and provider identifiers without provider-specific logic.
- The same helper can be invoked from POS without changing accounting semantics.

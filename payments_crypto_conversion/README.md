# Secure Crypto Transfers and Event Ledger

The retained technical addon name is upgrade compatibility only. Its business feature is an **outbound crypto transfer**. NOWPayments `/payout` transfers cryptocurrency to blockchain addresses; it is not fiat conversion, a bank cashout, or evidence of fiat proceeds.

## Ledger

* `crypto.asset` is the authoritative symbol + network (+ contract) identity. Legacy inventoried currencies migrate to `legacy-unknown`; administrators must select the real network before live use.
* `crypto.rate.snapshot` retains exact decimal quote evidence and becomes immutable when consumed. It never modifies daily `res.currency.rate`.
* `crypto.provider.event` is an append-only, SHA-256-addressed callback envelope.
* `crypto.settlement` is the normalized inbound/outbound economic event. Exact quantities are digit-only atomic-unit strings. Confirmed records can only be corrected by reversal.

External requests use stable UUID idempotency keys. Submission is protected by a PostgreSQL row lock; an ambiguous timeout enters `submission_unknown` and is never automatically retried. Accounting is allowed only after every transfer line has a terminal `finished` event whose HMAC signature was verified.

## IPN security

Configure a unique provider callback UUID and IPN secret. NOWPayments callbacks post to `/payment/nowpayments/ipn/<provider_uuid>`. Nested JSON is recursively key-sorted and compactly encoded, then checked with HMAC-SHA512 and constant-time comparison. Browser returns only redirect to the payment status page and never establish settlement.

## Local mock test

Create an administrator-only provider with code `mock_crypto`, environment **Mock**, and a mock IPN secret; create a network-aware asset and transfer route. Operators can submit transfers, and administrators can advance the mock event. Mock references are deterministic from the immutable UUIDs, mock processing uses the same signed event service, and no HTTP client is invoked. The banner/environment in transfer/provider screens distinguishes mock, test, and live records.

## Security

Viewer, Operator, Accountant, and Administrator groups provide separated duties. Company record rules apply to providers, routes, transfers, events, snapshots, and settlements. Only administrators can access credential fields. For live use select environment-variable credential storage and supply variable names; secrets are read at runtime.

## Limitations

Fiat conversion is not included. Full tax-lot policy expansion and wallet reconciliation remain future phases. Existing FIFO inventory support from `account_cryptocurrency` is retained temporarily.

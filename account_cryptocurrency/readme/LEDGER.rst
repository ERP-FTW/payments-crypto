Crypto settlement ledger and transfers
======================================

``account_cryptocurrency`` is the single provider-neutral foundation for crypto
inventory, exact settlement evidence, and outbound transfer orchestration.
Provider addons extend its provider interface. NOWPayments ``/payout`` transfers
cryptocurrency to blockchain addresses; it is not fiat conversion, a bank
cashout, or evidence of fiat proceeds.

Ledger models
-------------

* ``crypto.asset`` is authoritative network-aware asset identity.
* ``crypto.rate.snapshot`` retains exact decimal quote evidence and never writes
  provider quotes into daily ``res.currency.rate`` records.
* ``crypto.provider.event`` is an append-only, SHA-256-addressed callback envelope.
* ``crypto.settlement`` is the normalized inbound or outbound economic event.
  Exact quantities are digit-only atomic-unit strings.

Providers use stable UUID idempotency keys. Transfer submission is protected by
a PostgreSQL row lock. An ambiguous timeout enters ``submission_unknown`` and is
not automatically retried. Accounting is eligible only after terminal provider
evidence has passed signature verification.

Provider interface
------------------

Provider addons inherit ``crypto.transfer.provider`` and implement submission,
status refresh, and signed-event normalization. The base addon includes a
no-network ``mock_crypto`` implementation so provider behavior can be tested
without external credentials or real funds.

IPN security
------------

NOWPayments callbacks post to
``/payment/nowpayments/ipn/<provider_uuid>``. Nested JSON is recursively sorted,
compactly serialized, and verified with HMAC-SHA512 using constant-time
comparison. Browser return routes never establish settlement.

Security
--------

Viewer, Operator, Accountant, and Administrator groups separate provider
configuration, submission, evidence review, and accounting. Company record
rules apply to all company-owned transfer and ledger records. Only
administrators may access credential fields. Live credentials can be read from
environment variables at runtime.

Limitations
-----------

Fiat conversion is not included. Full tax-lot policy expansion and wallet
reconciliation remain future work. FIFO inventory and the settlement ledger are
maintained together in ``account_cryptocurrency``.

# Test matrix

| Area | Required tests |
| --- | --- |
| Repository reset | Manifest validity, XML load, missing assets, duplicate technical module names, install chain, uninstall chain. |
| `crypto_base` exact quantities | BTC satoshi conversion, 18-decimal token conversion, values larger than 32-bit integer, exact addition/subtraction, exact serialization/deserialization. |
| `crypto_base` evidence | Duplicate provider events, consumed snapshot immutability, append-only processed events, overpayment/underpayment preservation. |
| `crypto_base` multi-company | Company-aware record rules, cross-company wallet rejection, asset/network mismatch rejection. |
| Settlement workflow | Draft/quoted/pending/confirmed/failed/canceled/reversed transitions, no journal entry creation in provider-neutral module. |
| `account_crypto` receipts | Retained BTC receipt, crypto-denominated receipt, immediate-fiat processor receipt, inbound lot creation. |
| FIFO/disposals | Partial FIFO disposal, disposal across multiple lots, insufficient inventory, deterministic oldest-lot ordering, proceeds allocated once. |
| Fees/transfers | Provider fee in fiat, provider fee in crypto, network fee in crypto, wallet transfer preserving lot basis. |
| Posting controls | Duplicate accounting call idempotency, reversal, retry after failure, locked period rejection, multi-company isolation. |
| Precision | Separate book/tax basis, exact rounding, zero residual quantities. |
| POS/payment integration | POS validation does not double-post crypto, session close does not duplicate settlement accounting, payment webhooks normalize events without journal entries. |

# ADR-008: Reversal and immutable evidence

Status: accepted.

Processed provider events are append-only. Consumed rate snapshots and confirmed settlements cannot have economic evidence edited in place. Corrections use reversal flows: reverse journal entries, reverse crypto subledger moves, create new provider events/snapshots/settlements where needed, and preserve the original evidence chain.

After an accounting move is posted, no direct mutation of balances, lots, disposals, or consumed quantities is allowed. Idempotent retry APIs return existing posted artifacts; they do not duplicate journal entries, settlements, lots, disposal records, or provider events.

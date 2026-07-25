# ADR-007: Basis and disposal policy

Status: accepted.

Maintain separate book basis and tax basis on lots and disposal lines. The initial operational method is FIFO: consume the oldest eligible lots first, deterministically ordered by acquisition Datetime and record ID, supporting exact partial-lot consumption. Specific identification and pooled methods are placeholders that must raise clear validation errors until implemented.

Disposal records allocate proceeds once across consumed lots. Each disposal line records atomic units, allocated proceeds, released book basis, released tax basis, book gain/loss, and tax gain/loss. This avoids duplicating full proceeds on every source lot and keeps book/tax reporting independently extensible.

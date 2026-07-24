# ADR-004: Rate evidence

Status: accepted.

`res.currency.rate` remains useful for ordinary daily foreign-exchange rates and Odoo's standard currency conversion features, but it is not transaction-level evidence for crypto settlements. Crypto checkout quotes and provider settlement rates are immutable snapshots linked to a purpose and evidence payload.

`crypto.rate.snapshot` records company, asset, fiat currency, quoted Datetime, expiry Datetime, source, source pair, exact fiat-per-crypto, exact crypto-per-fiat, optional fiat amount, optional atomic units, provider reference, raw payload hash, purpose, and state. Once consumed, economically significant fields are immutable. Corrections create superseding snapshots or reversals; they do not mutate consumed evidence.

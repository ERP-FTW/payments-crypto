# ADR-006: Crypto ownership scenarios

Status: accepted.

- Merchant retains crypto: settlement debits crypto asset and credits fiat clearing/receivable at immutable settlement value; lots are created.
- Provider immediately converts to fiat: merchant never owns crypto; settlement debits processor receivable or bank clearing and credits fiat clearing/receivable; no crypto lot is created.
- Provider owes merchant a receivable: debit processor clearing/receivable and credit sales/payment clearing until fiat payout reconciliation.
- Invoice denominated in crypto: invoice may use a crypto-linked commercial currency only where legally/accounting-appropriate; settlement still records exact atomic units and snapshots. Company-currency balances use explicit snapshot values, not reconstructed daily rates.
- Wallet-to-wallet transfer: move atomic units between wallets, preserve lot basis, recognize network fee separately if paid in crypto, and do not recognize disposal gain/loss for self-transfer except consumed fee lots.

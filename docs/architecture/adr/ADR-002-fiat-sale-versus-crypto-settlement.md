# ADR-002: Fiat sale versus crypto settlement

Status: accepted.

A fiat-denominated POS order or invoice remains denominated, taxed, rounded, receipted, and reconciled in fiat. Crypto settlement is separate evidence that records exact atomic units, provider identifiers, confirmation state, and company-currency value at settlement.

For a $100 POS sale paid in BTC where the merchant retains crypto, the POS order remains a $100 sale. A linked `crypto.settlement` records, for example, `requested_atomic_units = 250000`, `received_atomic_units = 250000`, `fiat_amount = 100.00`, the BTC asset, wallet, provider evidence, quote snapshot, and settlement snapshot. Accounting clears the fiat POS receivable/payment clearing and recognizes the crypto asset at the settlement value; it does not rewrite the sale as a BTC-denominated sale.

Provider settlement values are not daily FX conversions. The settlement snapshot is transaction evidence: who quoted it, when, for which pair, which raw payload hash, what fiat amount and atomic units, and whether the merchant owns the crypto or only a processor receivable.

# Posting scenarios

All examples assume USD company currency. Exact atomic units live on settlements/lots; journal entries use company-currency debits and credits.

## 1. Fiat POS sale, merchant retains crypto

Sale/order accounting remains standard POS fiat accounting. On settlement confirmation for a $100 sale received as BTC:

| Account | Debit | Credit |
| --- | ---: | ---: |
| Crypto asset - BTC | 100.00 |  |
| POS/card/payment clearing |  | 100.00 |

Balanced total: debit 100.00, credit 100.00.

## 2. Crypto-denominated receipt

For an invoice denominated commercially in crypto with company-currency value of $250:

| Account | Debit | Credit |
| --- | ---: | ---: |
| Crypto asset | 250.00 |  |
| Accounts receivable |  | 250.00 |

Balanced total: debit 250.00, credit 250.00.

## 3. Provider converts immediately to fiat

Merchant never owns crypto; provider owes fiat $98 after a $2 fee from a $100 sale:

| Account | Debit | Credit |
| --- | ---: | ---: |
| Processor receivable | 98.00 |  |
| Provider fee expense | 2.00 |  |
| POS/card/payment clearing |  | 100.00 |

Balanced total: debit 100.00, credit 100.00.

## 4. Provider fee in fiat

Separate fiat fee charged after settlement:

| Account | Debit | Credit |
| --- | ---: | ---: |
| Provider fee expense | 3.00 |  |
| Processor receivable / bank clearing |  | 3.00 |

Balanced total: debit 3.00, credit 3.00.

## 5. Provider or network fee in crypto

Fee consumes BTC lot basis $1.20 with no separate proceeds:

| Account | Debit | Credit |
| --- | ---: | ---: |
| Network fee expense | 1.20 |  |
| Crypto asset - BTC |  | 1.20 |

Balanced total: debit 1.20, credit 1.20.

## 6. Outbound crypto spend

Spend crypto with $80 carrying basis for $95 vendor payment value:

| Account | Debit | Credit |
| --- | ---: | ---: |
| Accounts payable / expense clearing | 95.00 |  |
| Crypto asset |  | 80.00 |
| Realized gain |  | 15.00 |

Balanced total: debit 95.00, credit 95.00.

## 7. Wallet-to-wallet transfer preserving basis

Transfer crypto with $50 basis between company wallets and a $1 network fee:

| Account | Debit | Credit |
| --- | ---: | ---: |
| Crypto asset - destination wallet | 50.00 |  |
| Network fee expense | 1.00 |  |
| Crypto asset - source wallet |  | 51.00 |

Balanced total: debit 51.00, credit 51.00. If wallet-level accounting is represented only in the subledger, the journal entry may contain just the fee line pair while `crypto.asset.move.line` records the basis-preserving transfer.

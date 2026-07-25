{
    "name": "NOWPayments Crypto Payouts",
    "version": "18.0.2.0.0",
    "summary": "Verified NOWPayments outbound crypto transfer adapter",
    "category": "Accounting",
    "author": "Miler",
    "license": "AGPL-3",
    "depends": [
        "payments_crypto_conversion",
        "base",
        "account",
        "payment",
    ],
    "data": [
        "views/nowpayments_provider_views.xml",
    ],
    "installable": True,
    "application": False,
}

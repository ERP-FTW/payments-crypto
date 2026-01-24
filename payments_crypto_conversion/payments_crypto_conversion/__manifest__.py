{
    "name": "Payments Crypto Conversion",
    "version": "18.0.1.0.0",
    "summary": "Crypto cashout payout skeleton using outbound payments",
    "category": "Accounting",
    "author": "Miler",
    "license": "AGPL-3",
    "depends": [
        "base",
        "account",
        "payment",
        "account_cryptocurrency",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cashout_sequence.xml",
        "views/cashout_provider_views.xml",
        "views/cashout_config_views.xml",
        "views/cashout_payout_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
}

# Copyright 2021 ForgeFlow S.L.
# Copyright 2018 Fork Sand Inc.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Account Cryptocurrency",
    "version": "18.0.2.0.0",
    "category": "Account",
    "author": "ForgeFlow," "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/currency",
    "summary": "Crypto inventory, immutable settlement ledger, and transfer orchestration",
    "license": "AGPL-3",
    "depends": [
        "account",
        "payment",
        "point_of_sale",
    ],
    "data": [
        "security/account_cryptocurrency_security.xml",
        "security/crypto_transfer_security.xml",
        "security/ir.model.access.csv",
        "data/res_currency_move_sequence.xml",
        "data/crypto_transfer_sequence.xml",
        "views/res_currency_view.xml",
        "views/res_currency_move_menuitem.xml",
        "views/res_currency_move_view.xml",
        "views/res_currency_move_line_view.xml",
        "views/account_payment_view.xml",
        "views/crypto_transfer_provider_views.xml",
        "views/crypto_transfer_config_views.xml",
        "views/crypto_transfer_views.xml",
        "views/crypto_ledger_views.xml",
        "views/crypto_menu.xml",
    ],
}

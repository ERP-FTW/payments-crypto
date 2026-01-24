{
    "name": "Currency Valuation Reporting",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "summary": "Reporting tools for cryptocurrency inventory valuation",
    "license": "AGPL-3",
    "author": "ForgeFlow, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/currency",
    "depends": ["account_cryptocurrency"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_currency_reporting_views.xml",
    ],
    "installable": True,
}

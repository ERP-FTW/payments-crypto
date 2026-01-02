{
    "name": "MLR ecommerce BTCPay",
    "summary": "MLR ecommerce BTCPay",
    "author": "MLR - MI Lightning Rod",
    "website": "https://www.milightningrod.com",
    "category": "Ecommerce",
    "version": "17.0",
    "images": ["static/description/icon.png"],
    "depends": ["website", "mlr_ecommerce_cryptopayments"],
    "data": [
        "views/btcpay_payment_template.xml",
        "data/btcpay_payment_provider_data.xml",
        "data/btcpay_payment_method_data.xml",
        "views/btcpay_payment_form.xml",
        "views/btcpay_payment_provider.xml",

    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    "license": "LGPL-3",
}

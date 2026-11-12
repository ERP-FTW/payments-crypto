# -*- coding: utf-8 -*-
{
    'name': 'POS Crypto Payments',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Integrate your POS with Crypto on-chain and payments',
    'description': '',
    'depends': ['point_of_sale','account','pos_restaurant'],
    'data': [
        "views/pos_payment.xml",
        "views/pos_payment_method.xml",
    ],
    'installable': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'mlr_pos_cryptopayments/static/src/js/**/*.js',
            'mlr_pos_cryptopayments/static/src/xml/**/*.xml',
            'mlr_pos_cryptopayments/static/src/scss/**/*.scss',
        ],
    },
    'license': 'LGPL-3',
}

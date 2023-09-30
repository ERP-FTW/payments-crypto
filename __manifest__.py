# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'POS Bitcoin Payments Now',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Integrate your POS with a large number of on-chain cryptocurrencies',
    'description': '',
    'data': [
        'views/pos_payment_method.xml',
    ],
    'depends': ['point_of_sale','mlr_pos_cryptopayments'],
    'installable': True,
    'assets': {
        'point_of_sale.assets': [
            'mlr_pos_nowpayments/static/**/*',
            'mlr_pos_nowpayments/static/**/**/*',
        ],
    },
    'license': 'LGPL-3',
}

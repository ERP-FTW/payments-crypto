# -*- coding: utf-8 -*-
{
    'name': 'MLR POS Bitcoin Payments - Phoenixd',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'sequence': 7,
    'summary': 'Integrate your POS with Bitcoin lightning payments using Phoenixd',
    'description': '',
    'data': [
        'views/pos_payment_method.xml',
    ],
    'depends': ['point_of_sale', 'mlr_pos_cryptopayments'],
    'installable': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'mlr_pos_phoenixd/static/src/js/models.js',
            'mlr_pos_phoenixd/static/src/js/payment_phoenixd.js',
            'mlr_pos_phoenixd/static/src/js/payment_screen.js',
        ],
    },
    'license': 'LGPL-3',
}

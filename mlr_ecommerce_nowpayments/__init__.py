from . import models
from . import controllers

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(env, registry):
    setup_provider(env.cr, registry, 'now')


def uninstall_hook(env, registry):
    reset_payment_provider(env.cr, registry, 'now')

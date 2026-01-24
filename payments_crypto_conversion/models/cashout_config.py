from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CryptoCashoutConfig(models.Model):
    _name = "crypto.cashout.config"
    _description = "Crypto Cashout Configuration"
    _order = "priority, id"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    crypto_currency_id = fields.Many2one(
        "res.currency",
        required=True,
        domain=[("inventoried", "=", True)],
        string="Crypto Currency",
    )
    cashout_provider_id = fields.Many2one(
        "crypto.cashout.provider",
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    crypto_journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain=[("type", "in", ("bank", "cash"))],
        string="Crypto Journal",
    )
    cashout_partner_id = fields.Many2one(
        "res.partner",
        required=True,
        default=lambda self: self._get_or_create_cashout_partner(self.env.company).id,
        domain="['|', ('company_id', '=', company_id), ('company_id', '=', False)]",
        string="Cashout Partner",
    )
    fiat_currency_id = fields.Many2one("res.currency", string="Fiat Currency")
    bank_journal_id = fields.Many2one("account.journal", string="Bank Journal")
    clearing_account_id = fields.Many2one("account.account", string="Clearing Account")
    priority = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.model
    def _get_or_create_cashout_partner(self, company):
        cashout_name = "Crypto Cashout"
        partner = self.env["res.partner"].search(
            [
                ("name", "=", cashout_name),
                "|",
                ("company_id", "=", company.id),
                ("company_id", "=", False),
            ],
            limit=1,
        )
        if not partner:
            partner = self.env["res.partner"].create(
                {
                    "name": cashout_name,
                    "company_id": company.id,
                    "supplier_rank": 1,
                }
            )
        return partner

    @api.depends("company_id", "crypto_currency_id", "cashout_provider_id", "priority")
    def _compute_name(self):
        for rec in self:
            parts = [rec.company_id.display_name, rec.crypto_currency_id.display_name]
            if rec.cashout_provider_id:
                parts.append(rec.cashout_provider_id.display_name)
            rec.name = " / ".join(filter(None, parts))

    @api.onchange("company_id")
    def _onchange_company_id(self):
        for rec in self:
            if rec.company_id:
                rec.cashout_partner_id = self._get_or_create_cashout_partner(rec.company_id)

    @api.constrains(
        "crypto_journal_id", "crypto_currency_id", "company_id", "cashout_provider_id"
    )
    def _check_crypto_journal_currency(self):
        for rec in self:
            journal = rec.crypto_journal_id
            currency = rec.crypto_currency_id
            provider = rec.cashout_provider_id
            if not journal or not currency:
                continue
            if journal.type not in ("bank", "cash"):
                raise ValidationError(
                    _("The crypto journal must be of type Bank or Cash.")
                )
            if journal.currency_id != currency:
                raise ValidationError(
                    _(
                        "The crypto journal currency (%(journal)s) must match the crypto currency (%(currency)s)."
                    )
                    % {
                        "journal": journal.currency_id.display_name or _("not set"),
                        "currency": currency.display_name,
                    }
                )
            if journal.company_id != rec.company_id:
                raise ValidationError(
                    _("The crypto journal company must match the configuration company.")
                )
            if provider and provider.company_id != rec.company_id:
                raise ValidationError(
                    _("The cashout provider company must match the configuration company.")
                )

    _sql_constraints = [
        (
            "cashout_config_currency_company_uniq",
            "unique(company_id, crypto_currency_id)",
            "Only one cashout configuration is allowed per company and crypto currency.",
        )
    ]

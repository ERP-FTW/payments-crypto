import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class CryptoCashoutPayout(models.Model):
    _name = "crypto.cashout.payout"
    _description = "Crypto Cashout Payout"
    _order = "id desc"

    name = fields.Char(required=True, default=lambda self: _("New"), copy=False)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    config_id = fields.Many2one(
        "crypto.cashout.config",
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    cashout_provider_id = fields.Many2one(
        "crypto.cashout.provider",
        related="config_id.cashout_provider_id",
        store=True,
        readonly=True,
    )
    crypto_currency_id = fields.Many2one(
        "res.currency",
        related="config_id.crypto_currency_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("canceled", "Canceled"),
        ],
        default="draft",
        required=True,
    )
    provider_payout_id = fields.Char(index=True, copy=False)
    requested_at = fields.Datetime()
    created_at = fields.Datetime()
    updated_at = fields.Datetime()
    note = fields.Text()
    withdrawal_ids = fields.One2many(
        "crypto.cashout.withdrawal",
        "payout_id",
        string="Withdrawals",
        copy=True,
    )
    account_payment_id = fields.Many2one(
        "account.payment",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    res_currency_move_ids = fields.One2many(
        related="account_payment_id.res_currency_move_ids",
        readonly=True,
    )
    withdrawal_count = fields.Integer(compute="_compute_counts")
    currency_move_count = fields.Integer(compute="_compute_counts")

    @api.depends("withdrawal_ids", "res_currency_move_ids")
    def _compute_counts(self):
        for payout in self:
            payout.withdrawal_count = len(payout.withdrawal_ids)
            payout.currency_move_count = len(payout.res_currency_move_ids)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("crypto.cashout.payout") or _("New")
            config = None
            if vals.get("config_id"):
                config = self.env["crypto.cashout.config"].browse(vals["config_id"])
                vals.setdefault("company_id", config.company_id.id)
            if vals.get("withdrawal_ids") and config:
                currency_code = (config.crypto_currency_id.name or "").upper()
                normalized_lines = []
                for command in vals["withdrawal_ids"]:
                    if command[0] == 0 and command[2] is not None:
                        line_vals = dict(command[2])
                        line_vals.setdefault("currency_code", currency_code)
                        line_vals.setdefault("currency_id", config.crypto_currency_id.id)
                        normalized_lines.append((0, 0, line_vals))
                    else:
                        normalized_lines.append(command)
                vals["withdrawal_ids"] = normalized_lines
        return super().create(vals_list)

    @api.onchange("config_id")
    def _onchange_config_id(self):
        for payout in self:
            if not payout.config_id:
                continue
            payout.company_id = payout.config_id.company_id
            currency = payout.config_id.crypto_currency_id
            if currency and payout.withdrawal_ids:
                currency_code = (currency.name or "").upper()
                for line in payout.withdrawal_ids:
                    line.currency_code = currency_code
                    line.currency_id = currency

    @api.constrains("config_id", "company_id")
    def _check_config_company(self):
        for payout in self:
            if payout.config_id.company_id != payout.company_id:
                raise ValidationError(
                    _("The payout company must match the configuration company.")
                )

    def _ensure_withdrawals_currency(self):
        for payout in self:
            currency = payout.crypto_currency_id
            if not currency:
                continue
            expected_code = (currency.name or "").upper()
            bad_lines = payout.withdrawal_ids.filtered(
                lambda w: w.currency_code and w.currency_code != expected_code
            )
            if bad_lines:
                raise UserError(
                    _(
                        "All withdrawals must use currency code %(code)s for payout %(payout)s."
                    )
                    % {"code": expected_code, "payout": payout.display_name}
                )

    def _get_outbound_amount_crypto(self):
        self.ensure_one()
        self._ensure_withdrawals_currency()
        amount = sum(self.withdrawal_ids.mapped("amount"))
        if amount <= 0:
            raise UserError(_("The payout must have a strictly positive total amount."))
        return amount

    def _get_outbound_payment_method_line(self, journal):
        method_line = journal.outbound_payment_method_line_ids[:1]
        if not method_line:
            raise UserError(
                _(
                    "Journal %(journal)s has no outbound payment method lines. Configure one before posting the cashout."
                )
                % {"journal": journal.display_name}
            )
        return method_line

    def action_submit_to_provider(self):
        for payout in self:
            if payout.state not in ("draft", "submitted", "processing"):
                raise UserError(
                    _(
                        "Only draft or in-progress payouts can be submitted. Current state: %(state)s"
                    )
                    % {"state": payout.state}
                )
            payout.cashout_provider_id.provider_create_payout(payout)
            if not payout.requested_at:
                payout.requested_at = fields.Datetime.now()
            if payout.state == "draft":
                payout.state = "submitted"
        return True

    def action_refresh_status(self):
        for payout in self:
            if not payout.provider_payout_id:
                raise UserError(
                    _("Provider payout ID is required before refreshing the status.")
                )
            payout.cashout_provider_id.provider_get_payout(payout)
            payout.updated_at = fields.Datetime.now()
        return True

    def _validate_before_post_outflow(self):
        self.ensure_one()
        if self.account_payment_id:
            raise UserError(_("A crypto outflow payment has already been posted."))
        if not self.config_id:
            raise UserError(_("A cashout configuration is required."))
        config = self.config_id
        currency = config.crypto_currency_id
        journal = config.crypto_journal_id
        if not currency:
            raise UserError(_("The cashout configuration must define a crypto currency."))
        if not currency.inventoried:
            raise UserError(
                _(
                    "Currency %(currency)s is not inventoried. Enable inventoried FIFO valuation first."
                )
                % {"currency": currency.display_name}
            )
        if not journal:
            raise UserError(_("The cashout configuration must define a crypto journal."))
        if journal.currency_id != currency:
            raise UserError(
                _(
                    "Crypto journal %(journal)s must use currency %(currency)s."
                )
                % {"journal": journal.display_name, "currency": currency.display_name}
            )
        if journal.company_id != self.company_id:
            raise UserError(
                _("Crypto journal company must match the payout company.")
            )
        if not config.cashout_partner_id:
            raise UserError(_("The cashout configuration must define a cashout partner."))

    def action_post_crypto_outflow_payment(self):
        payments = self.env["account.payment"]
        for payout in self:
            payout._validate_before_post_outflow()
            config = payout.config_id
            journal = config.crypto_journal_id
            amount = payout._get_outbound_amount_crypto()
            method_line = payout._get_outbound_payment_method_line(journal)
            payment_date = (
                fields.Date.to_date(payout.requested_at)
                if payout.requested_at
                else fields.Date.context_today(payout)
            )
            ref = _("CASHOUT %(name)s%(provider)s") % {
                "name": payout.name,
                "provider": (
                    f" / {payout.provider_payout_id}" if payout.provider_payout_id else ""
                ),
            }
            payment_vals = {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": config.cashout_partner_id.id,
                "amount": amount,
                "currency_id": payout.crypto_currency_id.id,
                "journal_id": journal.id,
                "payment_method_line_id": method_line.id,
                "date": payment_date,
                "ref": ref,
                "company_id": payout.company_id.id,
            }
            payment = payments.create(payment_vals)
            payment.action_post()
            payout.account_payment_id = payment

            currency_moves = payment.res_currency_move_ids
            if not currency_moves:
                _logger.warning(
                    "No currency moves were created for payout %s (payment %s).",
                    payout.display_name,
                    payment.display_name,
                )
            elif any(move.direction != "outbound" for move in currency_moves):
                _logger.warning(
                    "Currency moves for payout %s are not all outbound: %s",
                    payout.display_name,
                    currency_moves.mapped("direction"),
                )

            if payout.state not in ("done", "failed", "canceled"):
                payout.state = "processing"

        if len(self) == 1:
            return self.action_open_payment()
        return True

    def action_open_payment(self):
        self.ensure_one()
        if not self.account_payment_id:
            raise UserError(_("No payment is linked to this payout yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Crypto Outflow Payment"),
            "res_model": "account.payment",
            "view_mode": "form",
            "res_id": self.account_payment_id.id,
            "target": "current",
        }

    def action_open_currency_moves(self):
        self.ensure_one()
        action = self.account_payment_id.button_currency_moves()
        action["name"] = _("Currency Moves")
        return action

from odoo import fields, models, tools


class ResCurrencyInventoryReport(models.Model):
    _name = "res.currency.inventory.report"
    _description = "Currency Inventory Position"
    _auto = False
    _rec_name = "currency_id"

    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    company_currency_id = fields.Many2one("res.currency", readonly=True)
    qty_in = fields.Float(string="Total Received Qty", readonly=True)
    qty_out = fields.Float(string="Total Sent Qty", readonly=True)
    remaining_qty = fields.Float(string="Remaining Qty", readonly=True)
    inbound_value = fields.Monetary(
        string="Received Value", currency_field="company_currency_id", readonly=True
    )
    outbound_cost_value = fields.Monetary(
        string="Sent Cost Basis", currency_field="company_currency_id", readonly=True
    )
    inventory_value = fields.Monetary(
        string="Inventory Value", currency_field="company_currency_id", readonly=True
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %(table)s AS (
                SELECT
                    row_number() OVER (ORDER BY move.company_id, move.currency_id) AS id,
                    move.company_id,
                    move.currency_id,
                    company.currency_id AS company_currency_id,
                    SUM(CASE WHEN move.direction = 'inbound' THEN line.quantity ELSE 0 END) AS qty_in,
                    SUM(CASE WHEN move.direction = 'outbound' THEN line.quantity ELSE 0 END) AS qty_out,
                    SUM(CASE WHEN move.direction = 'inbound' THEN line.remaining_qty ELSE 0 END) AS remaining_qty,
                    SUM(CASE WHEN move.direction = 'inbound' THEN line.amount ELSE 0 END) AS inbound_value,
                    SUM(CASE WHEN move.direction = 'outbound' THEN line.amount ELSE 0 END) AS outbound_cost_value,
                    SUM(
                        CASE WHEN move.direction = 'inbound'
                            THEN line.remaining_qty * line.price_unit
                            ELSE 0
                        END
                    ) AS inventory_value
                FROM res_currency_move_line line
                JOIN res_currency_move move ON move.id = line.move_id
                JOIN res_company company ON company.id = move.company_id
                GROUP BY move.company_id, move.currency_id, company.currency_id
            )
            """
            % {"table": self._table}
        )


class ResCurrencyGainLossReport(models.Model):
    _name = "res.currency.gain.loss.report"
    _description = "Currency Realized Gain/Loss"
    _auto = False
    _order = "disposal_date desc, id desc"

    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    company_currency_id = fields.Many2one("res.currency", readonly=True)
    payment_id = fields.Many2one("account.payment", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    payment_ref = fields.Char(readonly=True)
    payment_date = fields.Date(readonly=True)
    disposal_date = fields.Date(readonly=True)
    in_move_line_id = fields.Many2one("res.currency.move.line", readonly=True)
    in_date = fields.Date(readonly=True)
    in_price_unit = fields.Monetary(
        string="Inbound Price Unit",
        currency_field="company_currency_id",
        readonly=True,
    )
    quantity = fields.Float(string="Disposed Qty", readonly=True)
    cost_basis = fields.Monetary(
        string="Cost Basis", currency_field="company_currency_id", readonly=True
    )
    proceeds = fields.Monetary(
        string="Proceeds", currency_field="company_currency_id", readonly=True
    )
    gain_loss = fields.Monetary(
        string="Gain/Loss", currency_field="company_currency_id", readonly=True
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %(table)s AS (
                SELECT
                    line.id,
                    move.company_id,
                    move.currency_id,
                    company.currency_id AS company_currency_id,
                    move.payment_id,
                    payment.partner_id,
                    payment.ref AS payment_ref,
                    payment.date AS payment_date,
                    line.date AS disposal_date,
                    line.in_move_line_id,
                    in_line.date AS in_date,
                    in_line.price_unit AS in_price_unit,
                    line.quantity,
                    line.amount AS cost_basis,
                    COALESCE(SUM(ABS(aml.balance)), 0.0) AS proceeds,
                    COALESCE(SUM(ABS(aml.balance)), 0.0) - line.amount AS gain_loss
                FROM res_currency_move_line line
                JOIN res_currency_move move ON move.id = line.move_id
                JOIN res_company company ON company.id = move.company_id
                LEFT JOIN res_currency_move_line in_line ON in_line.id = line.in_move_line_id
                LEFT JOIN account_payment payment ON payment.id = move.payment_id
                LEFT JOIN account_journal journal ON journal.id = payment.journal_id
                LEFT JOIN account_move account_move ON account_move.id = payment.move_id
                LEFT JOIN account_move_line aml
                    ON aml.move_id = account_move.id AND aml.account_id = journal.default_account_id
                WHERE move.direction = 'outbound'
                GROUP BY
                    line.id,
                    move.company_id,
                    move.currency_id,
                    company.currency_id,
                    move.payment_id,
                    payment.partner_id,
                    payment.ref,
                    payment.date,
                    line.date,
                    line.in_move_line_id,
                    in_line.date,
                    in_line.price_unit,
                    line.quantity,
                    line.amount
            )
            """
            % {"table": self._table}
        )


class ResCurrencyReconciliationReport(models.Model):
    _name = "res.currency.reconciliation.report"
    _description = "Currency Payment Reconciliation"
    _auto = False
    _rec_name = "payment_id"
    _order = "payment_date desc, id desc"

    payment_id = fields.Many2one("account.payment", readonly=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("cancel", "Cancelled"),
        ],
        readonly=True,
    )
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    company_currency_id = fields.Many2one("res.currency", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    payment_ref = fields.Char(readonly=True)
    payment_type = fields.Selection(
        selection=[("inbound", "Inbound"), ("outbound", "Outbound")], readonly=True
    )
    payment_date = fields.Date(readonly=True)
    payment_amount_currency = fields.Float(readonly=True)
    crypto_received_qty = fields.Float(readonly=True)
    crypto_sent_qty = fields.Float(readonly=True)
    inbound_value = fields.Monetary(
        string="Inbound Value", currency_field="company_currency_id", readonly=True
    )
    outbound_cost_value = fields.Monetary(
        string="Outbound Cost Basis",
        currency_field="company_currency_id",
        readonly=True,
    )
    crypto_value = fields.Monetary(
        string="Crypto Value", currency_field="company_currency_id", readonly=True
    )
    payment_value_company_currency = fields.Monetary(
        string="Payment Value",
        currency_field="company_currency_id",
        readonly=True,
    )
    disposal_gain_loss = fields.Monetary(
        string="Disposal Gain/Loss",
        currency_field="company_currency_id",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %(table)s AS (
                WITH payment_value AS (
                    SELECT
                        payment.id AS payment_id,
                        COALESCE(SUM(ABS(aml.balance)), 0.0) AS payment_value
                    FROM account_payment payment
                    JOIN account_journal journal ON journal.id = payment.journal_id
                    JOIN account_move account_move ON account_move.id = payment.move_id
                    LEFT JOIN account_move_line aml
                        ON aml.move_id = account_move.id AND aml.account_id = journal.default_account_id
                    GROUP BY payment.id
                )
                SELECT
                    row_number() OVER (ORDER BY move.payment_id) AS id,
                    move.payment_id,
                    move.state,
                    move.company_id,
                    move.currency_id,
                    company.currency_id AS company_currency_id,
                    payment.partner_id,
                    payment.ref AS payment_ref,
                    payment.payment_type,
                    payment.date AS payment_date,
                    payment.amount AS payment_amount_currency,
                    SUM(CASE WHEN move.direction = 'inbound' THEN line.quantity ELSE 0 END) AS crypto_received_qty,
                    SUM(CASE WHEN move.direction = 'outbound' THEN line.quantity ELSE 0 END) AS crypto_sent_qty,
                    SUM(CASE WHEN move.direction = 'inbound' THEN line.amount ELSE 0 END) AS inbound_value,
                    SUM(CASE WHEN move.direction = 'outbound' THEN line.amount ELSE 0 END) AS outbound_cost_value,
                    SUM(line.amount) AS crypto_value,
                    COALESCE(payment_value.payment_value, 0.0) AS payment_value_company_currency,
                    COALESCE(payment_value.payment_value, 0.0)
                        - SUM(CASE WHEN move.direction = 'outbound' THEN line.amount ELSE 0 END) AS disposal_gain_loss
                FROM res_currency_move move
                JOIN res_currency_move_line line ON line.move_id = move.id
                JOIN res_company company ON company.id = move.company_id
                JOIN account_payment payment ON payment.id = move.payment_id
                LEFT JOIN payment_value ON payment_value.payment_id = move.payment_id
                WHERE move.payment_id IS NOT NULL
                GROUP BY
                    move.payment_id,
                    move.state,
                    move.company_id,
                    move.currency_id,
                    company.currency_id,
                    payment.partner_id,
                    payment.ref,
                    payment.payment_type,
                    payment.date,
                    payment.amount,
                    payment_value.payment_value
            )
            """
            % {"table": self._table}
        )

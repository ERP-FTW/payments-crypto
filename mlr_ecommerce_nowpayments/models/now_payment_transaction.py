import logging
from datetime import timedelta

from werkzeug.urls import url_encode

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL, float_compare

_logger = logging.getLogger(__name__)

# NOWPayments payment_status values, as documented by the provider.
# `finished` is the only final success: the funds reached the merchant's wallet.
STATUS_DONE = ('finished',)
# Seen or confirmed on chain, or being forwarded, but not yet received by the merchant.
STATUS_PENDING = ('waiting', 'confirming', 'confirmed', 'sending')
STATUS_CANCEL = ('failed', 'expired', 'refunded')
# The buyer sent less than the price. Money moved, so this is neither done nor cancelled.
STATUS_PARTIAL = ('partially_paid',)

# How long after creation an open transaction is still reconciled by the scheduled job.
# NOWPayments expires an unpaid payment after 7 days.
RECONCILE_WINDOW_DAYS = 8
RECONCILE_PAGE_SIZE = 100
RECONCILE_MAX_PAGES = 5


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # `crypto_invoice_id` and `crypto_payment_link` are declared by mlr_ecommerce_cryptopayments.

    def _get_specific_rendering_values(self, processing_values):
        """Render the redirect form that asks Odoo to open the NOWPayments invoice.

        Only the reference is posted. The invoice amount and currency are read back from this
        transaction on the server, never from the browser.
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'now':
            return res
        return {
            'reference': self.reference,
            'api_url': '/payment/now/createInvoice',
        }

    # === Invoice creation === #

    def _nowpayments_invoice_payload(self):
        self.ensure_one()
        # get_base_url() may end with a slash (a website domain does); a doubled slash in the
        # callback path would not route.
        base_url = self.provider_id.get_base_url().rstrip('/')
        return {
            'price_amount': self.amount,
            'price_currency': self.currency_id.name.lower(),
            'order_id': self.reference,
            'order_description': self.reference,
            'ipn_callback_url': f"{base_url}/payment/now/ipn",
            'success_url': f"{base_url}/payment/now/return?{url_encode({'ref': self.reference})}",
            'cancel_url': f"{base_url}/payment/now/return?{url_encode({'ref': self.reference})}",
        }

    def _nowpayments_get_invoice_url(self):
        """Return the hosted invoice URL for this transaction, creating the invoice once.

        A resubmitted checkout reuses the invoice already opened for the transaction instead of
        creating a second one the buyer could also pay.
        """
        self.ensure_one()
        if self.provider_code != 'now':
            raise ValidationError(_("NOWPayments: transaction %s is not a NOWPayments transaction.",
                                    self.reference))
        # Two overlapping checkouts of the same transaction must not each open an invoice. The
        # second one waits on this row lock; once this request commits, Odoo retries it (the row
        # changed under its snapshot) and it then reuses the invoice stored here.
        self.env.cr.execute(SQL("SELECT id FROM payment_transaction WHERE id = %s FOR UPDATE", self.id))
        self.invalidate_recordset(['state', 'crypto_invoice_id', 'crypto_payment_link'])
        if self.state not in ('draft', 'pending'):
            raise ValidationError(_("NOWPayments: transaction %(ref)s is already %(state)s.",
                                    ref=self.reference, state=self.state))
        if self.crypto_invoice_id and self.crypto_payment_link:
            return self.crypto_payment_link

        provider = self.provider_id
        if self.amount < provider.crypto_min_amount or (
            provider.crypto_max_amount and self.amount > provider.crypto_max_amount
        ):
            raise ValidationError(_(
                "NOWPayments: %(amount)s is outside the range accepted for this provider.",
                amount=self.amount,
            ))

        content = provider._nowpayments_make_request(
            '/v1/invoice', payload=self._nowpayments_invoice_payload(), method='POST',
        )
        invoice_id = content.get('id')
        invoice_url = content.get('invoice_url')
        if not invoice_id or not invoice_url:
            raise ValidationError(_("NOWPayments: the invoice response has no id or URL."))
        payment_method = self.env['payment.method']._get_from_code('nowpayments')
        self.write({
            'crypto_invoice_id': str(invoice_id),
            'crypto_payment_link': invoice_url,
            'crypto_payment': True,
            'payment_method_id': payment_method.id or self.payment_method_id.id,
        })
        return invoice_url

    # === Notification handling === #

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'now' or len(tx) == 1:
            return tx

        reference = notification_data.get('order_id')
        if not reference:
            raise ValidationError("NOWPayments: " + _("Received data with missing order id."))
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'now')])
        if not tx:
            raise ValidationError(
                "NOWPayments: " + _("No transaction found matching reference %s.", reference))
        return tx

    def _process_notification_data(self, notification_data):
        """Apply the provider's verified state to the transaction.

        `notification_data` only says which payment to look at. Status, amount and currency are
        re-read from NOWPayments with this transaction's provider, so neither the browser nor the
        body of a callback can confirm a payment.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'now':
            return

        payment_id = notification_data.get('payment_id')
        if not payment_id:
            raise ValidationError("NOWPayments: " + _("Received data with missing payment id."))
        verified = self.provider_id._nowpayments_make_request(f'/v1/payment/{payment_id}')
        self._nowpayments_apply_verified_payment(verified)

    def _nowpayments_check_identity(self, payment):
        """Refuse a payment that belongs to another order or another invoice."""
        self.ensure_one()
        if str(payment.get('order_id') or '') != self.reference:
            raise ValidationError(_(
                "NOWPayments: payment %(payment)s belongs to order %(order)s, not %(ref)s.",
                payment=payment.get('payment_id'), order=payment.get('order_id'), ref=self.reference,
            ))
        invoice_id = payment.get('invoice_id')
        if self.crypto_invoice_id and invoice_id and str(invoice_id) != self.crypto_invoice_id:
            raise ValidationError(_(
                "NOWPayments: payment %(payment)s belongs to invoice %(invoice)s, not %(expected)s.",
                payment=payment.get('payment_id'), invoice=invoice_id,
                expected=self.crypto_invoice_id,
            ))

    def _nowpayments_amount_mismatch(self, payment):
        """Return a message when the provider's price differs from this transaction, else None."""
        self.ensure_one()
        currency = (payment.get('price_currency') or '').upper()
        try:
            amount = float(payment.get('price_amount'))
        except (TypeError, ValueError):
            amount = None
        if currency != self.currency_id.name.upper() or amount is None or float_compare(
            amount, self.amount, precision_rounding=self.currency_id.rounding
        ) != 0:
            return _(
                "NOWPayments: amount mismatch. The provider reports %(amount)s %(currency)s for this "
                "payment, but the transaction is %(expected)s %(expected_currency)s. The payment was "
                "not confirmed.",
                amount=payment.get('price_amount'), currency=currency or '?',
                expected=self.amount, expected_currency=self.currency_id.name,
            )
        return None

    def _nowpayments_apply_verified_payment(self, payment):
        self.ensure_one()
        self._nowpayments_check_identity(payment)

        status = payment.get('payment_status')
        payment_id = str(payment.get('payment_id') or '')
        if self.state == 'done' and self.provider_reference and self.provider_reference != payment_id:
            # A second payment against a settled order (the buyer paid twice). Never re-apply.
            _logger.warning(
                "NOWPayments: ignoring payment %s (%s) for %s, already settled by payment %s",
                payment_id, status, self.reference, self.provider_reference,
            )
            return

        self.write({
            'provider_reference': payment_id,
            'crypto_payment': True,
            'crypto_payment_type': payment.get('pay_currency') or self.crypto_payment_type,
            'crypto_invoiced_crypto_amount': float(payment.get('pay_amount') or 0.0),
        })
        if payment.get('pay_amount'):
            try:
                self.crypto_conversion_rate = float(payment['price_amount']) / float(payment['pay_amount'])
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        if status in STATUS_DONE:
            mismatch = self._nowpayments_amount_mismatch(payment)
            if mismatch:
                self._set_error(mismatch)
            else:
                self._set_done()
        elif status in STATUS_PENDING:
            self._set_pending(state_message=_("NOWPayments status: %s", status))
        elif status in STATUS_CANCEL:
            self._set_canceled(state_message=_("NOWPayments status: %s", status))
        elif status in STATUS_PARTIAL:
            self._set_error(_(
                "NOWPayments: the buyer paid %(paid)s %(coin)s of %(due)s %(coin)s (partially paid). "
                "Resolve with the buyer; the order was not confirmed.",
                paid=payment.get('actually_paid'), due=payment.get('pay_amount'),
                coin=(payment.get('pay_currency') or '').upper(),
            ))
        else:
            _logger.warning("NOWPayments: unknown status %s for %s", status, self.reference)
            self._set_error(_("NOWPayments: unknown payment status %s.", status))

    # === Reconciliation (return page and scheduled job) === #

    def _nowpayments_list_invoice_payments(self):
        """Return this transaction's payments, found through its own invoice id."""
        self.ensure_one()
        found = {}
        date_from = (self.create_date - timedelta(days=1)).strftime('%Y-%m-%d')
        for page in range(RECONCILE_MAX_PAGES):
            query = url_encode({
                'limit': RECONCILE_PAGE_SIZE, 'page': page, 'sortBy': 'created_at',
                'orderBy': 'desc', 'invoiceId': self.crypto_invoice_id, 'dateFrom': date_from,
            })
            content = self.provider_id._nowpayments_make_request(f'/v1/payment/?{query}', jwt=True)
            rows = content.get('data') or []
            for row in rows:
                # Correlate on our side as well; never rely on the listing filter alone.
                if str(row.get('invoice_id') or '') == self.crypto_invoice_id \
                        and str(row.get('order_id') or '') == self.reference:
                    found[str(row.get('payment_id'))] = row
            if len(rows) < RECONCILE_PAGE_SIZE:
                break
        return list(found.values())

    def _nowpayments_reconcile(self):
        """Settle this transaction from the provider's current state, if it has a payment yet."""
        self.ensure_one()
        if self.provider_code != 'now' or not self.crypto_invoice_id:
            return
        payments = self._nowpayments_list_invoice_payments()
        if not payments:
            return

        def rank(row):
            status = row.get('payment_status')
            if status in STATUS_DONE:
                return 0
            if status in STATUS_PARTIAL:
                return 1
            if status in STATUS_PENDING:
                return 2
            return 3
        best = sorted(payments, key=rank)[0]
        self._handle_notification_data('now', {
            'order_id': self.reference, 'payment_id': best.get('payment_id'),
        })

    @api.model
    def _cron_nowpayments_reconcile(self):
        """Complete payments whose notification never arrived and whose buyer never returned."""
        limit_date = fields.Datetime.now() - timedelta(days=RECONCILE_WINDOW_DAYS)
        txs = self.search([
            ('provider_code', '=', 'now'),
            ('state', 'in', ('draft', 'pending')),
            ('crypto_invoice_id', '!=', False),
            ('create_date', '>=', limit_date),
        ])
        for tx in txs:
            try:
                with self.env.cr.savepoint():
                    tx._nowpayments_reconcile()
            except ValidationError as error:
                _logger.warning("NOWPayments: could not reconcile %s: %s", tx.reference, error)

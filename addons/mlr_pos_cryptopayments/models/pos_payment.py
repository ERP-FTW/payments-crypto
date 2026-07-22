from odoo import api, fields, models, _
from odoo.tools import formatLang, float_is_zero
from odoo.exceptions import ValidationError, UserError
try:
   import qrcode
except ImportError:
   qrcode = None
try:
   import base64
except ImportError:
   base64 = None
from io import BytesIO

class PosPayment(models.Model):
   _inherit = "pos.payment"

   SATS_PER_BTC = 100000000

   is_crypto_payment = fields.Boolean('Paid with Crypto')
   cryptopay_payment_type = fields.Char('Crypto payment Type')
   cryptopay_invoice_id = fields.Char('CryptoPay Invoice ID')
   conversion_rate = fields.Float('Conversion rate')
   invoiced_crypto_amount = fields.Float('Invoiced Crypto Amount', digits=(12,8))
   fiat_currency_id = fields.Many2one('res.currency', string='Fiat Currency')
   crypto_currency_id = fields.Many2one('res.currency', string='Crypto Currency')
   crypto_amount_currency = fields.Monetary(
      string='Crypto Amount',
      currency_field='crypto_currency_id',
   )
   crypto_rate = fields.Float('Crypto Rate')
   crypto_rate_datetime = fields.Datetime('Crypto Rate Datetime')
   requested_sat_amount = fields.Integer('Requested Sats')
   received_sat_amount = fields.Integer('Received Sats')
   provider_fee_sat = fields.Integer('Provider Fee Sats')
   provider_status = fields.Char('Provider Status')
   provider_completed_at = fields.Datetime('Provider Completed At')
   provider_raw_json = fields.Text('Provider Raw JSON')
   cryptopay_payment_link = fields.Char('CryptoPay Payment Link')
   cryptopay_payment_link_qr_code = fields.Binary('QR Code', compute="_generate_qr") #binary field that is computed into a QR

   def _get_default_crypto_currency(self):
      return self.env['res.currency'].search([('name', '=', 'BTC')], limit=1)

   def _sync_crypto_currency_vals(self, vals):
      vals = dict(vals)
      pos_order_id = vals.get('pos_order_id')
      if pos_order_id and not vals.get('fiat_currency_id'):
         order = self.env['pos.order'].browse(pos_order_id)
         vals['fiat_currency_id'] = order.currency_id.id

      has_crypto_data = any(vals.get(field) for field in (
         'crypto_amount_currency',
         'crypto_rate',
         'requested_sat_amount',
         'received_sat_amount',
         'provider_status',
         'provider_completed_at',
         'provider_raw_json',
         'conversion_rate',
         'invoiced_crypto_amount',
      ))
      if has_crypto_data and not vals.get('crypto_currency_id'):
         btc_currency = self._get_default_crypto_currency()
         if btc_currency:
            vals['crypto_currency_id'] = btc_currency.id

      if vals.get('crypto_rate') and not vals.get('conversion_rate'):
         vals['conversion_rate'] = vals['crypto_rate']
      elif vals.get('conversion_rate') and not vals.get('crypto_rate'):
         vals['crypto_rate'] = vals['conversion_rate']
      if vals.get('crypto_rate') and not vals.get('crypto_rate_datetime'):
         vals['crypto_rate_datetime'] = fields.Datetime.now()

      sat_amount = vals.get('received_sat_amount') or vals.get('requested_sat_amount')
      if sat_amount and not vals.get('crypto_amount_currency'):
         vals['crypto_amount_currency'] = float(sat_amount) / self.SATS_PER_BTC

      if vals.get('crypto_amount_currency') and not vals.get('invoiced_crypto_amount'):
         vals['invoiced_crypto_amount'] = vals['crypto_amount_currency']
      elif vals.get('invoiced_crypto_amount') and not vals.get('crypto_amount_currency'):
         vals['crypto_amount_currency'] = vals['invoiced_crypto_amount']

      return vals

   @api.model_create_multi
   def create(self, vals_list):
      vals_list = [self._sync_crypto_currency_vals(vals) for vals in vals_list]
      return super().create(vals_list)

   def write(self, vals):
      vals = self._sync_crypto_currency_vals(vals)
      return super().write(vals)

   def _export_for_ui(self,payment):
      payment_fields = super(PosPayment, self)._export_for_ui(payment)
      payment_fields.update({
         'is_crypto_payment': payment.is_crypto_payment,
         'cryptopay_invoice_id': payment.cryptopay_invoice_id,
         'cryptopay_payment_type': payment.cryptopay_payment_type,
         'cryptopay_payment_link': payment.cryptopay_payment_link,
         'invoiced_crypto_amount': payment.invoiced_crypto_amount,
         'conversion_rate': payment.conversion_rate,
         'fiat_currency_id': payment.fiat_currency_id.id,
         'crypto_currency_id': payment.crypto_currency_id.id,
         'crypto_amount_currency': payment.crypto_amount_currency,
         'crypto_rate': payment.crypto_rate,
         'crypto_rate_datetime': payment.crypto_rate_datetime,
         'requested_sat_amount': payment.requested_sat_amount,
         'received_sat_amount': payment.received_sat_amount,
         'provider_fee_sat': payment.provider_fee_sat,
         'provider_status': payment.provider_status,
         'provider_completed_at': payment.provider_completed_at,
         'provider_raw_json': payment.provider_raw_json,
         })
      return payment_fields

   def _generate_qr(self): #called by compute field to change binary into QR
       for rec in self:
           if qrcode and base64:
               qr = qrcode.QRCode(
                   version=1,
                   error_correction=qrcode.constants.ERROR_CORRECT_L, #use low error correction to keep QR less complex and small
                   box_size=8,
                   border=4,
               )
               qr.add_data(rec.cryptopay_payment_link)
               qr.make(fit=True)
               img = qr.make_image()
               temp = BytesIO()
               img.save(temp, format="PNG")
               qr_image = base64.b64encode(temp.getvalue())
               rec.update({'cryptopay_payment_link_qr_code': qr_image}) #update the field with QR
           else:
               raise UserError(_('Necessary Requirements To Run This Operation Is Not Satisfied'))
   



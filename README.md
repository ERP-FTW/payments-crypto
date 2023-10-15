# mlr_ecommerce_nowpayments

Lightning Rod Ecommerce Now Payments Readme

Overview
<br>This custom module for Odoo 16+ adds BTCpay server as a payment provider to the Ecommerce application. BTCpay server is a potentially self-hosted Bitcoin payment gateway/provider which is queried by API calls from Odoo. BTCpay server account access by API is provided to Odoo and a Bitcoin onchain/lightning option is added to the customer by checkout portal link. If the Bitcoin payment option is selected by a customer, they are forwarded to a BTCpay site with a created invoice and QR code for payment. After the payment is confirmed the customer can be redirected back to the Odoo online store receipt page and the order is registered and queued.

Prerequisites (versions)
<br>Compatible with Odoo 16
<br>Postgres 14+
<br>BTCpay server with API access
<br>mlr_ecommerce_cryptopayments custom module

Installation (see this video for tutorial on Odoo module installation)
1. Download repository and place extracted folder in the Odoo addons folder.
2. Login to Odoo database to upgrade and enable developer mode under settings.
3. Under apps Update the App list.
4. Search for the module (MLR) and install.

Setup

1. In Odoo navigate to Website-> Ecommerce -> Payment Providers.

2. Click on BTCpay to open the record.
3. Enter a Name for the Instance. 
4. Login into your BTCpay server and navigate to Account -> API Key. Create a key for use with Odoo.
5. From BTCpay server copy the following information and paste in the Odoo Instance record: the server base URL, API key, and store ID. Enter a minimum and maximum fiat amount.
6. Click Connect to BTCpay to verify the information is correct. If it is correct a green popup will affirm so, if it is incorrect a red popup will appear.
   
7. In Configuration -> Payment Form select the icon for lightning, in Configuration -> Payment Followup select the Payment Journal.
   
8. Select Enable to make BTCpay instance a current method and save (the first time a new Accounting Journal BTCpay will be created and used for recording transactions).
9. To have an invoice automatically created which will show the payment was post go to Website -> Configuration -> Settings -> Invoicing -> Automatic Invoicing.
10. Activate the Sales application if wishing to use online payment links for Invoices. Enable Sales -> Configuration -> Settings -> Quotations & Orders -> Online Payment.
   

Operation
Online Shop
1. A customer will navigate to the Shop section of the website and add items to the cart. After initiating the checkout and filling in customer information the available payment methods will be displayed.
   
2. The customer can select the Bitcoin option and directions will appear below.
   
3. After clicking Pay Now  the customer will be taken to a BTCpay server page with the invoice and QR code to be paid.
   
4. The customer scans the QR code or pastes the invoice text as a send from their wallet.
    
5. Upon BTCpay server confirmation of the order the customer will have a button to click or be returned automatically to the receipt page of the Odoo site.
  
6. Odoo will process the order and create a sales order for fulfillment.



Invoicing
1. Create a quote from Sales -> Orders -> Quotes -> New. Enter the customer, timeframe, and product information. Create the quote and send to a customer.
  
2. Confirm the quote once accepted to change status to a Sales Order.
  
3. Click Create Invoice to make the invoice for Billing. Select your preferred options.

4. Create the payment link to send to the customer for online payment with Action > Generate a Payment Link.
   
5. Copy the payment link and use the Send & Print button to convey to the customer.

6. Visiting the payment link will show the enabled online payment providers.

7. The customer will be taken to the third-party site and returned upon payment. The customer will be taken to a payment confirmation page and have access to a customer account history portal if they have an account.
   
8. Viewing the invoice will show that it is paid.



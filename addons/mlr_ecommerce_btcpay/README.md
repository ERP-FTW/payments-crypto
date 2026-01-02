# mlr_ecommerce_btcpay_2
Lightning Rod Ecommerce BTCpay Readme

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
![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/8bd7f17a-add0-494d-90d5-38735129364e)
2. Click on BTCpay to open the record.
3. Enter a Name for the Instance. 
4. Login into your BTCpay server and navigate to Account -> API Key. Create a key for use with Odoo.
5. From BTCpay server copy the following information and paste in the Odoo Instance record: the server base URL, API key, and store ID. Enter a minimum and maximum fiat amount.
6. Click Connect to BTCpay to verify the information is correct. If it is correct a green popup will affirm so, if it is incorrect a red popup will appear.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/cf84a790-de85-41ba-bedb-824ebbd00016)
7. In Configuration -> Payment Form select the icon for lightning, in Configuration -> Payment Followup select the Payment Journal.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/9b31408a-1e3b-40c7-8253-1811787a7b42)
8. Select Enable to make BTCpay instance a current method and save (the first time a new Accounting Journal BTCpay will be created and used for recording transactions).
9. To have an invoice automatically created which will show the payment was post go to Website -> Configuration -> Settings -> Invoicing -> Automatic Invoicing.
10. Activate the Sales application if wishing to use online payment links for Invoices. Enable Sales -> Configuration -> Settings -> Quotations & Orders -> Online Payment.
   

Operation
Online Shop
1. A customer will navigate to the Shop section of the website and add items to the cart. After initiating the checkout and filling in customer information the available payment methods will be displayed.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/ee9e9ae1-9eca-4d8b-afe4-b0683b0729c8)
2. The customer can select the Bitcoin option and directions will appear below.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/979ccc7a-e692-42f1-aeee-92621530f9cb)
3. After clicking Pay Now  the customer will be taken to a BTCpay server page with the invoice and QR code to be paid.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/28e4b94f-c636-4d19-a12b-e6780ab5f590)
4. The customer scans the QR code or pastes the invoice text as a send from their wallet.
    ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/95a44dfc-4f6e-445e-83b0-9aa68b59a978)
5. Upon BTCpay server confirmation of the order the customer will have a button to click or be returned automatically to the receipt page of the Odoo site.
  ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/53ca67fe-1ba4-4e0d-944d-3799f482b959)
6. Odoo will process the order and create a sales order for fulfillment.
![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/e5914109-5665-4dd9-99f1-1becea9c77e4)


Invoicing
1. Create a quote from Sales -> Orders -> Quotes -> New. Enter the customer, timeframe, and product information. Create the quote and send to a customer.
  ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/eff035f9-d5cf-44e2-91fc-bdc5111200fe)
2. Confirm the quote once accepted to change status to a Sales Order.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/4f302c98-ec98-40e1-a6b3-42aa888d330e)
3. Click Create Invoice to make the invoice for Billing. Select your preferred options.
![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/994d1b0e-b572-4521-8b6e-0debaaca3f41)
4. Create the payment link to send to the customer for online payment with Action > Generate a Payment Link.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/82adeeaa-123f-4749-ae1c-af1648f10761)
5. Copy the payment link and use the Send & Print button to convey to the customer.
![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/a882dece-61a0-49f0-a02b-981c43847843)
6. Visiting the payment link will show the enabled online payment providers.
![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/12ae758b-dc11-4755-9128-eb964dec1920)
7. The customer will be taken to the third-party site and returned upon payment. The customer will be taken to a payment confirmation page and have access to a customer account history portal if they have an account.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/6b6f2dc2-7c86-44cd-bebe-92f7d7cb04e7)
8. Viewing the invoice will show that it is paid.
![image](https://github.com/ERP-FTW/mlr_ecommerce_btcpay_2/assets/124227412/21b2bbba-e9f0-4f48-9fd5-7a98609ad0d2)

 

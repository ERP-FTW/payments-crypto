# mlr_ecommerce_nowpayments

Lightning Rod Ecommerce Now Payments Readme

Overview
<br>This custom module for Odoo 16+ adds NowPayments as a payment provider to the Ecommerce application.  NowPayments acts as a payment gateway/provider for a large number of cryptocurrencies and will also convert between chains based on your preference. NowPayments account access by API is provided to Odoo and a cryptocurrency option is added to the customer checkout. If the cryptocurrency payment option is selected by a customer, they are forwarded to a NowPayments site with a created invoice and QR code for payment. After the payment is confirmed the customer can be redirected back to the Odoo online store receipt page and the order is registered and queued.

Prerequisites (versions)
<br>Compatible with Odoo 16
<br>Postgres 14+
<br>NowPayments account with API access
<br>mlr_ecommerce_cryptopayments custom module

Installation (see this video for tutorial on Odoo module installation)
1. Download repository and place extracted folder in the Odoo addons folder.
2. Login to Odoo database to upgrade and enable developer mode under settings.
3. Under apps Update the App list.
4. Search for the module (MLR) and install.

Setup

1. In Odoo navigate to Website-> Ecommerce -> Payment Providers.
![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/742b4021-f496-4673-8568-1883b69956bc)
2. Click on Now to open the record.
3. Enter a Name for the Instance. 
4. Login into your NowPayments account and navigate to Account -> API Key. Create a key for use with Odoo.
5. From NowPayments copy the following information and paste in the Odoo Instance record: the server base URL, API key, user name and password. Enter a minimum and maximum fiat amount.
6. Click Connect to Now to verify the information is correct. If it is correct a green popup will affirm so, if it is incorrect a red popup will appear.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/6de1b7ab-54ca-46c4-a524-8c6f211793e3)
7. In Configuration -> Payment Form select the icon for lightning, in Configuration -> Payment Followup select the Payment Journal.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/37800745-9667-42d0-8b3e-b5d6472b3111)
8. Select Enable to make NowPayments a current method and save.
9. To have an invoice automatically created which will show the payment was post go to Website -> Configuration -> Settings -> Invoicing -> Automatic Invoicing.
10. To enable online payment of invoices go to Invoicing -> Configuration -> Settings -> Customer Payments -> Invoice Online Payment.
11. Activate the Sales application if wishing to use online payment links for Invoices. Enable Sales -> Configuration -> Settings -> Quotations & Orders -> Online Payment.
   

Operation
Online Shop
1. A customer will navigate to the Shop section of the website and add items to the cart. After initiating the checkout and filling in customer information the available payment methods will be displayed.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/e4497110-17f1-4c3f-9de3-66b4dfc84e98)
2. The customer can select the Now Payments option and directions will appear below.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/49a7eab2-8941-40cb-b9fa-a7ce2ff496a7)
3. After clicking Pay Now  the customer will be taken to a BTCpay server page with the invoice and QR code to be paid.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/bb953be5-df62-4d02-ba48-555116e7b84a)
4. The customer scans the QR code or pastes the invoice text as a send from their wallet.
    ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/a0793c83-89e9-4e76-a2c5-7cdfa8dd85e5)
5. Upon BTCpay server confirmation of the order the customer will have a button to click or be returned automatically to the receipt page of the Odoo site.
  ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/52c2b95c-54f5-43e6-a056-63d861c34ca1)
6. Odoo will process the order and create a sales order for fulfillment.
![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/f026d7ea-6c83-4f70-a87c-03eb0f317141)




Invoicing
1. Create a quote from Sales -> Orders -> Quotes -> New. Enter the customer, timeframe, and product information. Create the quote and send to a customer.
![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/31acbffe-a791-483d-a27e-4f5de1b1aa55)
2. Confirm the quote once accepted to change status to a Sales Order.
  ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/1e47717a-04e8-45a7-adbf-67063279a0ad)
3. Click Create Invoice to make the invoice for Billing. Select your preferred options.
![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/f7e9ab59-be38-43c8-9107-9b46826f160e)
4. Create the payment link to send to the customer for online payment with Action > Generate a Payment Link.
   ![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/0342dccf-7db9-4441-b82b-8484902a907d)
5. Copy the payment link and use the Send & Print button to convey to the customer.
![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/6432c708-0589-4620-920d-ce45e6230d93)
6. Visiting the payment link will show the enabled online payment providers.
![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/a26c5aab-50f3-4fbd-847c-3598146442bf)
7. The customer will be taken to the third-party site with the option to select among cryptocurrencies.
![image](https://github.com/ERP-FTW/mlr_ecommerce_nowpayments/assets/124227412/79267081-3c9a-4bc1-888a-60a18a3b0077)
8. Upon completion of the payment process, the customer will be taken to a payment confirmation page and have access to a customer account history portal if they have an account.
   
10. Viewing the invoice will show that it is paid.



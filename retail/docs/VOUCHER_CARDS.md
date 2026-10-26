# Promotional voucher cards

Open **Promotions → Voucher Cards → Add Voucher Card Batch**.

1. Enter the title, company, value per card, quantity, start date and expiry date.
   Values are not restricted to denominations. AED 1 and AED 1,000,000,000,000
   are supported. The system rejects amounts that exceed its exact currency
   precision instead of rounding them. Quantity is entered by the operator;
   10,000 cards is supported through background chunks.
2. Keep All Products checked, or select eligible items, brands and categories.
   A match in any selected row qualifies; categories include descendants.
3. Check Activate All Cards to activate the batch, or leave it unchecked to
   generate Draft cards. Save, then click Generate Cards. Progress refreshes
   while the background worker runs. Resume Generation safely retries after
   an interrupted job. Keep at least one long-queue worker running.
4. View / Select Cards opens the card list. Select cards from one batch and use
   Actions → Activate Selected Cards. The same menu supports blocking and
   archiving. Unchecking Activate All Cards never deactivates issued cards.
   Active cards show Unused or Partially Used in the existing ledger.
5. Click **Print Format**. Choose the A4 card or label format, then set the logo,
   terms, card-number range (up to 500 per range) and label dimensions there.
   Use **Save & Preview** to open the printable cards. The selected format and
   batch printing settings are remembered. For individual/selected records use
   Voucher Card - Card or Voucher Card - Label in the ledger's normal Print menu.
6. The same Print Format dialog includes separate **HTML** and **CSS** editors.
   Edits use standard ERPNext Print Format permissions and affect batches using
   the selected format. The application ships separate Retail baselines; existing
   editable copies are never overwritten by migration.
7. At redemption, the cashier scans the QR code or enters the code. Partial
   redemption keeps the balance for the next visit. ERP invoices have an
   optional Voucher Card Redeem Amount field; leaving it zero uses the maximum
   eligible balance. A cancelled invoice restores its recorded redemption once.
8. Transaction History keeps one status document per card, showing its current
   status and balance plus the last action. Actions update this same document;
   they do not create additional event or Version records. Standard POS
   operation receipts retain redemption and reversal details.
   Archive expired or fully used cards to remove them from the batch's active
   card list. Their records and history remain for audit.

These batches issue **free promotional vouchers** using the existing invoice
voucher discount treatment. They do not implement paid prepaid gift-card sales,
liability accounting, cash change or reloading. The .NET terminal must use the
online card redemption additions in POS_API_CONTRACT.md; ERP-side support does
not update the separate terminal application automatically.

Implementation is entirely in Retail. It adds Retail DocTypes, widens only
Retail voucher monetary columns, and uses standard Frappe document permissions,
queues, invoices, printing and migrations. It does not edit Frappe/ERPNext core
or generate an additional Pricing Rule for a card balance.

## Activation date and time

Enable **Set Activation Times** on a new batch, then enter **Active From Date**,
**Active From Time**, **Active To Date**, and **Active To Time**. These define
one continuous validity period in the site timezone. For example, 22 October at
09:00 through 1 November at 17:00 includes all hours on the intervening days.
There is no recurring daily opening or closing time. Leave the checkbox off to
use whole dates, as before. The end date/time cannot precede the start date/time.
The period is copied to each card, locked when generation begins, and shown on
standard card print formats. Successful approval retries and subsequent sale
binding retain their original approval.

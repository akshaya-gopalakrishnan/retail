# Editable print formats

Edit each document's `- A4` Print Format in the site UI. HTML holds markup and
Jinja; Custom CSS holds format styling. These are code editors, not a visual
layout builder. Letter Head content and Frappe's base print styling remain separate.

Retail ships the twelve approved A4 designs in
`retail/templates/editable_print_formats/` as separate HTML and CSS files:
Sales Invoice, Delivery Note, Quotation, Sales Order, Supplier Quotation,
Purchase Order, Purchase Receipt, Purchase Invoice, Material Request,
POS Branch Day Closing, Payment Entry, and Journal Entry. Installation and migration create
missing A4 formats from these files with Standard set to No and Custom Format
enabled, then select them as defaults unless the site chose another format.

To distribute a later UI-approved design, copy its HTML and Custom CSS into the
matching files in that directory and release the app. A UI save by itself is
site-local. The older Print Format source records remain compatibility fallbacks.

A4 containers grow with their content instead of reserving a full page height.
Do not add `min-height: 270mm` to their CSS: with A4 margins, Chromium can round
that height beyond the printable area and produce an empty second sheet.
Long item lists still paginate normally; totals, notes, and signatures may also
require another page when the remaining printable space is insufficient.

`ensure_editable_print_formats` creates missing site-owned A4 copies, separates
embedded styles into Custom CSS, and sets the default unless the site chose a
different format. Existing A4 HTML and CSS are never rewritten on migration.
Existing sites therefore adopt a replacement design only through an explicit
site-level edit; preserve/export their current format first.

Purchase Order's shipped design prints Supplier Address Details on the left and
Shipping Address Details on the right. Select both addresses on the Purchase
Order; the format does not substitute the supplier's address for a missing
shipping address.

## Journal Entry

`Journal Entry - A4` matches the transaction letterhead, blue headings, and
signature lines. It prints the entry type, account and party display names,
references, row remarks, and separate debit/credit columns in company currency.
Foreign-currency rows additionally show their account-currency amounts and
exchange rate. Totals and amount in words use the saved company-currency debit
and credit values; currencies are never added together. Draft and cancelled
entries show their status, and a nonzero saved difference is displayed.
Printing reads the document without changing it or querying current balances.

Open **Print Format > Journal Entry - A4** to edit HTML and Custom CSS. The
editable copy is initially seeded from ERPNext's Journal Auditing Voucher using
Retail's packaged HTML/CSS. Site edits and a chosen different default survive
upgrades.

## Accounts Payable report

`Accounts Payable - A4` follows the same editable report-printing workflow as
Accounts Receivable. The Print/PDF menus use it by default, and **Edit Print
Format** opens its site-owned HTML and Custom CSS. Existing edits survive
installation and migration.

The layout shows supplier/party display names, voucher references, supplier
bill numbers/dates, invoiced and paid amounts, debit notes, outstanding balances,
and dynamic ageing buckets. Grouped supplier subtotals, payment terms, future
payments, and account currencies retain the report's values. Portrait,
landscape, letterhead, filters, and selected columns use the same controls as
Accounts Receivable. Printing does not change accounting records or balances.

## Accounts Receivable report

`Accounts Receivable - A4` is a site-owned **Report / JS** Print Format with
separate HTML and Custom CSS editors. The report's Print and PDF menus select
it by default and offer landscape/portrait, letterhead, filters, and column
selection. **Edit Print Format** opens the site's copy for permitted editors.
Existing site edits are preserved during installation and migration.

The default layout shows customer/party names, voucher references, invoiced,
paid, credit-note and outstanding amounts, plus the report's dynamic ageing
buckets. Portrait places additional values beneath each entry. Grouped
subtotals, payment terms, future payments, and party-currency rows retain the
report's values. Printing never recalculates balances or combines currencies.
Custom report layouts use Frappe's client-side JS template syntax rather than
document-format Jinja. The existing report filters, exports and accounting
calculations remain authoritative.

## Payment Entry

`Payment Entry - A4` uses the same letterhead, blue headings, centred title,
and signature lines as the transaction formats. Receive entries print as Receipt
Voucher, Pay entries as Payment Voucher, and Internal Transfer entries as Internal
Transfer Voucher. Draft and cancelled entries show their status prominently.
The allocation table and totals use the saved Payment Entry values; printing
does not query current invoice balances or change any transactions. Receipt and
payment totals use the party account currency, with the other account's amount
shown separately when it differs. Internal transfers show the source amount and,
when different, the destination amount. The editable copy is initially seeded
from ERPNext's Bank and Cash Payment Voucher using Retail's packaged HTML/CSS.

Open **Print Format > Payment Entry - A4** to edit HTML and Custom CSS, then save.
Existing site edits and a deliberately selected different default survive upgrades.

## POS Branch Day Closing

`POS Branch Day Closing - Retail` ships the default design and installation
creates `POS Branch Day Closing - A4` as a site-owned editable copy. Its HTML and
Custom CSS follow the same ownership rules as the transaction formats.

`retail.pos_day_closing_print.day_closing_print_data` reads saved cashier-shift
membership, submitted POS invoices, and submitted Receive/Pay Payment Entries.
Printing never refreshes, saves, reopens, or recalculates a closing. Sales,
invoice count, cash totals, payment-method totals, and settlement totals use the
closing's saved values. Category/tax and cashier/counter collection breakdowns
come from currently submitted source documents; differences from saved totals
are identified on the printout. Missing historical settlement snapshots are not
represented as known zero values. No denomination, delivery, or order-source
figures are invented.

# Editable print formats

Edit each document's `- A4` Print Format in the site UI. HTML holds markup and
Jinja; Custom CSS holds format styling. These are code editors, not a visual
layout builder. Letter Head content and Frappe's base print styling remain separate.

Retail ships independent HTML/CSS baselines for Sales Order, Supplier Quotation,
Purchase Order, Purchase Receipt, Purchase Invoice, and Material Request in
`retail/retail_app/print_format/`. To distribute a UI-approved design, copy its
HTML and Custom CSS into the corresponding shipped JSON definition and release
the app. A UI save by itself is site-local.

`ensure_editable_print_formats` creates missing site-owned A4 copies, separates
embedded styles into Custom CSS, and sets the default unless the site chose a
different format. Existing A4 HTML and CSS are never rewritten on migration.
Existing sites therefore adopt a replacement design only through an explicit
site-level edit; preserve/export their current format first.

Purchase Order's shipped design prints Supplier Address Details on the left and
Shipping Address Details on the right. Select both addresses on the Purchase
Order; the format does not substitute the supplier's address for a missing
shipping address.

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

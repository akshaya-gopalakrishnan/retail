# Transaction identity in reports

Retail adds sold/transaction UOM, recorded barcode, item/packing name, quantity in that UOM, conversion factor and identity source. Existing columns, row grouping, stock quantities, prices, valuation and accounting calculations retain their behavior. Quantity and conversion columns use Data formatting to avoid adding unlike UOMs or conversion factors in automatic report totals.

## Resolution and historical records

- Match the source child row, not Item Code alone. Stock Ledger resolves its SLE using movement dimensions and running balance, then follows `voucher_detail_no`. Serial/batch bundle splits use the exact bundle and the displayed movement share.
- Read saved invoice/transaction facts and the existing completed .NET payload. Resolve packing name by Item Code plus barcode, with UOM/conversion consistency checks. A present but unmatched barcode does not select another packing.
- A missing barcode stays **Not recorded**, even if the current master has only one barcode. A unique UOM/conversion match can supply a packing name; the source column explicitly identifies current Item setup as the source. Ambiguous identities retain the saved line name with an explanation.
- Follow `pos_invoice` + `pos_invoice_item` on consolidated Sales Invoice lines to retain original POS packing identity. Use the current line's signed stock quantity divided by the original conversion factor, including returns.
- Before new submissions, Retail saves a hidden, read-only, non-copyable JSON custom field, `custom_retail_transaction_identity`, on Sales Invoice Item, POS Invoice Item, Delivery Note Item, Purchase Invoice Item, Purchase Receipt Item and Stock Entry Detail. This freezes display identity against later master edits. No old invoices or receipts are rewritten.

## Report coverage

| Area | Presentation |
| --- | --- |
| Stock Ledger, Packing Stock Ledger | Additional transaction columns, preserving existing stock UOM and packing representations |
| Stock Movement Summary, Stock Adjustment History, Damaged and Expired Stock, Cashier Wise Damage, Supplier Wise Returns, Expiry Loss, Margin By Movement, Van Wastage Report | Additional transaction columns for source lines; reconciliation rows without transaction identity stay blank |
| POS Discount Report, POS Price Override Report, External POS Rate Audit, Van Detailed Sales Summary, Item-wise Sales Register, Gross Profit by Invoice | Additional sold columns on item rows |
| POS Item-wise Sales, POS Sales Summary, POS Invoice Profit, Daily Sales Summary, Daily Profit Report, Van Profit Report, Van Daily Sales Summary, Cashier Wise Sales, Counter Wise Sales, POS Hourly Sales, POS Category Item Group Sales, POS Daily Closing Summary, Counter Performance, Item Group Sales Analysis | Sold Packing Breakdown; grouping and totals preserved |
| POS Transaction Log, POS Return Report, Daily Transaction Log, Sales Register, Sales Tax Report, Purchase Tax Report, Tax Report | Packing breakdown of each invoice; existing invoice links provide document detail |
| Van Daily Stock Summary | Additional breakdown of its sales component |
| Gross Profit grouped views | Sold Packing Breakdown; existing totals preserved |

Stock balance, packing stock balance, reorder, expiry/batch balances, inventory ranking and payment/settlement-only reports retain their current meaning; these do not identify an individual sold packing. Existing invoice links remain available for drilldown. Financial summary rows without a source invoice have no fabricated sold identity.

Retail uses its existing Report subclass and report helpers. No Frappe or ERPNext source files are modified. Report execution adds fields before serialization, so fresh prepared reports and Excel exports include them. Previously generated prepared reports need regeneration to show the additional fields.

## Installation and validation

Install/migrate hooks create the custom fields idempotently on both existing and fresh sites. On an existing development site:

```sh
bench --site retail-test.localhost execute retail.transaction_identity.install
bench --site retail-test.localhost clear-cache
```

Tests: `retail.tests.test_transaction_identity`, `retail.tests.test_pos_item_names`, existing profitability VAT memo and Business Home profit-card regressions. Live validation compares original fields and row counts with the previous Retail code and exercises the report API, Excel generation and Desk.

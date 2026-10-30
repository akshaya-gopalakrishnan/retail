# Promotion Performance

Open Promotions → Promotion History → Promotion Performance. Choose dates,
company, branch, counter, cashier or promotion; switch between Summary and Detail.

This report covers submitted Offline POS invoices with recorded promotion evidence.
It does not infer promotion usage for older bills that omit that evidence.

Summary groups each promotion by company, counts distinct sales bills, return bills
and purchasing customer accounts, and shows net sales, promotion savings, posted
goods cost, gross profit and margin. Detail includes item/UOM quantities, free
quantities, invoice links and the reasons any profit is incomplete. Quantities
are not added across different UOMs in the summary.

Money is in company currency, excluding VAT. Cost comes from uncancelled stock
ledger entries for the exact invoice item, or its exact consolidated Sales Invoice
item. Stock movement quantity must match. Returns reverse sales and cost. Missing
stock entries, non-stock items, ambiguous shared promotion allocations, mismatched
posted sales/quantities and unverified promotion evidence leave profit blank.
A group with any incomplete rows has no cost/profit/margin total. Free item costs
are included when their invoice lines carry promotion evidence. Unattributed free
lines cannot be discovered automatically. Discounts are not subtracted twice.
Gross profit does not include campaign expenses or operating overhead.

Previous-period comparison uses an immediately preceding period of equal length.
It compares all sales of the observed promoted item/UOM pairs in both periods,
with identical company/branch/counter/cashier filters and invoice permissions.
A zero or negative baseline leaves percentage change blank. This is descriptive
sales growth, not proof that the promotion caused growth or incremental profit.
Customers are customer accounts and may include a shared walk-in account.
Multiple offers can attribute the same sales line: never sum promotion rows to
obtain company sales. Open the Detail view to review incomplete evidence.

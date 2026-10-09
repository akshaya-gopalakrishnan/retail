# Find Invoice

Open the POS Invoice or Sales Invoice list (or an invoice form) and click **Find Invoice**.
Enter an exact .NET `pos_bill_no` (including leading zeros) or ERP invoice ID, or combine
purchase date/time, customer, cashier, counter and branch filters. Invoice type defaults
to All. Filters are optional, but at least one search criterion is required.

Date/time boundaries are inclusive and use the system time zone. The finder searches
posting date/time, not sync creation time. The POS API preserves supplied posting dates
and times for future receipts. Historical invoices whose timestamps were previously
overwritten are not corrected by this feature; bills missing original timestamps cannot
be reconstructed by the search. The .NET client should always send `posting_date` and
`posting_time` with the original purchase values.

Sales Invoices created from POS receipts do not have the terminal metadata fields.
Selecting Sales Invoice follows matching, readable POS receipts to their readable
accounting invoices. The original POS receipt link and purchase details remain visible.
Ordinary Sales Invoices can be found by ERP invoice ID, customer and posting date/time.
Cancelled and draft documents are included with explicit status. Accounting invoices and
POS receipts remain separate documents, with links to identify the relationship.

The finder uses permission-aware list queries, including user restrictions; it does not
grant invoice, Employee or POS Branch Counter permissions. Link dropdowns use existing
master-data permissions, and readable master records provide cashier/counter names.
At most 100 results are shown, newest first. Narrow filters when more matches exist.
No migrations or new business fields are required.

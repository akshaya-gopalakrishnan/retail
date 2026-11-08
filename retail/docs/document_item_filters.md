# Document list item filters

Retail adds an Item selector to POS Invoice, Sales Invoice, Purchase Order,
Purchase Invoice, and Purchase Receipt lists. The four invoice/receipt lists also
have separate searchable Serial No and Batch No dropdowns. Select a number or
enter its complete value. When Item is selected, dropdown suggestions are limited
to that item's serial/batch masters. The filter X clears these controls together
with native list filters. Purchase Orders have no serial/batch inputs because their rows do not
store those identities.

Combined filters must match the same item row. Serial and batch identities match
either legacy row fields or the row's Serial and Batch Bundle entries. Linked
receipts, deliveries and other documents are not searched for item identities. Repeated matching
rows do not duplicate a document. Existing filters continue to apply; clearing
the Retail inputs restores the native list and count endpoints.

The implementation uses instance-local list handlers, Retail endpoints calling
native reportview, and request-scoped permission query conditions. It retains
native document and user permissions, validates the supported DocTypes and
permitted child fields, and does not change core apps or transaction records.
Filter inputs apply to the current list session; they are not stored as native
saved filters or copied to separate Report Builder/Data Export screens.

## Sales and purchase lists: Related Document

Quotation, Sales Order, Delivery Note, Sales Invoice, Supplier Quotation, Purchase
Order, Purchase Receipt, and Purchase Invoice share one **Related Document**
autocomplete in each list. Type the document ID and select a suggestion showing
its ID and type. Each list finds its own records connected in either direction,
including through intermediate documents and multiple receipts/invoices, using
existing saved transaction links.
For example, selecting a PO in the PI list finds invoices linked through its PRs even if their
item rows do not directly store the PO. Selecting an invoice includes that invoice
and other invoices in the same connected transaction chain. A source without
records of the current list's type shows no matches. Clearing filters restores
the normal list.

Supported search types: Purchase Invoice, Purchase Receipt, Purchase Order,
Supplier Quotation, Material Request, Sales Order, Delivery Note, Sales Invoice,
Quotation, Payment Entry, Payment Request, Journal Entry, Landed Cost Voucher,
Asset, and Auto Repeat. Shared suppliers, customers, items, accounts, and other
masters do not connect transactions. A payment referencing several documents can
connect their chains; returns and amendments are also connections.

The lookup follows readable Link and Dynamic Link fields on transactions and
their child tables. Native list permissions apply at every step and to final
rows/counts; unreadable intermediate documents stop that path. Other list filters
intersect the result. Chains exceeding 500 readable documents raise a clear
message instead of returning incomplete results. No records or schema are changed.
All eight lists use the same JavaScript, query/count endpoints, and connection
resolver. The original PI helper remains available for existing callers. List
scripts and permission hooks are appended to existing registrations. The five
original item-filter lists retain their existing Item/Serial No/Batch No controls;
the additional lists gain only Related Document. Search checks the current list's
read permission and does not require Purchase Invoice access for sales users.

The selected value is local to the list session, as with the existing Retail item
filters; it is not a saved filter or an export/report filter. Integration coverage:
`retail.tests.test_related_document_filters`.

Validation: `retail.tests.test_document_item_filters` uses synthetic parent and
child rows with rolled-back writes to test all five lists, counts, legacy and
bundle matches, exact serial matching, combined filters and permission rejection.

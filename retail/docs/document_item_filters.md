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
receipts, deliveries and other documents are not searched. Repeated matching
rows do not duplicate a document. Existing filters continue to apply; clearing
the Retail inputs restores the native list and count endpoints.

The implementation uses instance-local list handlers, Retail endpoints calling
native reportview, and request-scoped permission query conditions. It retains
native document and user permissions, validates the supported DocTypes and
permitted child fields, and does not change core apps or transaction records.
Filter inputs apply to the current list session; they are not stored as native
saved filters or copied to separate Report Builder/Data Export screens.

Validation: `retail.tests.test_document_item_filters` uses synthetic parent and
child rows with rolled-back writes to test all five lists, counts, legacy and
bundle matches, exact serial matching, combined filters and permission rejection.

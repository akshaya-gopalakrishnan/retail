# Product Conversion

Open **Items → Product Conversion**, immediately after **Brands**.
Both Source Warehouse and Target Warehouse default to `Stores - [company abbr]`
when that warehouse exists. They remain editable.

New documents use `PC-1`, `PC-2`, and so on, with a separate counter from POS
Counter public codes. Existing document IDs remain unchanged.

1. Use **Add Row** in the single **Items** table, like Journal Entry. Select
   the Main Item and Packing Item, enter **Qty to Generate** and **Qty to
   Consume** (in the main item's Stock UOM). For 20 × 50 ml packs from a main
   item stocked in litres, enter `20` to generate and `1` to consume.
2. Alternatively, click **Get Items from BOM**, select the BOM and generated
   quantity, and click **Get Items**. It fills the same Items table. Multiple
   BOMs and directly entered products can be mixed.
3. **Consumption Details** opens the selected product's materials when needed
   for extra bottles/caps, actual quantities, warehouses, batches or serials.
   There is no second consumption table on the main form. BOM material
   quantities scale automatically with the generated quantity.
4. Labour Cost and Packing Cost are **total extra charges for that product row**,
   in company currency. Consumed materials already contribute to Product Cost
   and must not be added again as extra packing charges. BOM operation charges
   are not added automatically.
5. Review current stock and costs. The row's expanded form includes the
   optional **Update Item Master Cost** checkbox and further stock details.
   Choose expense accounts for extra charges and use **Refresh Stock and
   Costs** when required. Save, then Submit to post.

`Total Cost = consumed material stock cost + labour cost + extra packing cost`.
Cost per Pack is Total Cost divided by generated quantity. Quantity changes
scale consumption according to Consumption per Finished Unit. All cost totals
are recalculated by the server; browser values are previews. Native stock
valuation at the posting date and selected batch determines posted values.
Combined requirements for a shared material are checked before posting.

Responsibility and Costs open or close when their headings are clicked. Remarks
starts as a small text field and grows with its contents. Drag an Items column
heading to reorder it, or drag its edge to resize; layouts use personal saved
column settings. The grid settings button also lets you choose visible columns.

## Posting and master cost

Submission creates and submits exactly one linked native **Repack Stock Entry**
within the same database transaction. Each product retains its own materials
and charges. Remaining bulk stock does not acquire the output's extra charges.
Native Stock Ledger and General Ledger posting remain responsible for stock
valuation, batches, serial numbers and accounting.

**Update Item Master Cost** defaults to unchecked. Checked products update the
finished Item's existing buying/reference cost through Retail's existing VAT
and price synchronization. Existing VAT-inclusive entry settings are respected.
Repeated checked rows for the same Item use their combined cost / quantity.
Unchecked products, source Item prices, selling prices and purchase-history
rates are not rewritten by conversion logic.

Cancel Product Conversion to cancel its linked Stock Entry. Direct cancellation
of the linked Stock Entry is blocked. Cancellation restores the prior master
cost only if the Item has not been edited since this conversion updated it;
a later edit is retained and reported to the user.

## View and print

After posting, **View** contains:

- Stock Ledger
- Accounting Ledger
- Serial and Batch Summary
- Stock Entry

Report filters use the linked Stock Entry voucher, including a voucher list for
Serial and Batch Summary. Report permissions remain native.

The editable **Product Conversion - A4** format shows company details, source
and target locations, responsible users, reference/date/status, each finished
product with quantities and costs, and that product's Consumption Details
immediately beneath it. It is the document's default print format.

BOMs with scrap/process loss require separate stock entries. Outputs cannot
also be consumed in the same conversion; use sequential conversions instead.

## Verification

Database-free cost tests:

```sh
env/bin/python -m unittest retail.tests.test_repack retail.tests.test_product_conversion -v
```

`validation/product_conversion_isolated.py` snapshots `retail-test.localhost`
read-only into a disposable MariaDB instance and uses a separate Redis instance.
It verifies real submit/cancel, stock balances and values, balanced GL, checked
and unchecked master updates, aggregate shortages, and native batch summary.
It does not change site configuration or run destructive Frappe test hooks.

`validation/product_conversion_browser.py` checks unsaved forms, both loaders,
stock display, scaling, sidebar placement and View routing in Chromium. A4 HTML,
PNG and PDF inspection artifacts are stored under `/tmp` during validation.

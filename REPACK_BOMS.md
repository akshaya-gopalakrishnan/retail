# Multiple BOMs in Repack

Open a draft **Stock Entry**, choose **Repack**, then enable **Multiple BOMs**
inside the existing **BOM Info** section.

1. Add each BOM and the finished quantity to produce. Quantity uses the finished
   item's Stock UOM, irrespective of the BOM's base output quantity.
2. Choose source and target warehouses in each BOM row, or use the document's
   Default Warehouses. Loading resolves defaults onto each BOM row, so they
   remain available after ERPNext clears the document's warehouse defaults.
3. Enter **Extra Packing Cost (Total)** for each BOM row. This is the total
   extra charge for that production quantity, in company currency. Packaging
   materials already present in the BOM are consumed as materials; do not add
   their value again here. BOM operation costs are not automatically added.
4. For extra charges, choose an expense account in company currency under
   **Packing Cost Account**. Native Additional Costs rows credit this account.
5. Click **Get Items from BOMs**, review materials, outputs and any required
   batches/serials in the existing Items table, then save and submit normally.

Reloading replaces generated items after confirmation, including manual changes
and batch/serial selections. Remove existing Serial and Batch Bundles first.
Existing manually entered items must be cleared explicitly before loading.
After changing BOM, quantity, BOM-row warehouse or explosion settings, reload
the items. Editing packing charges only requires saving to recalculate costs.

## Costing

Each BOM group keeps its own material rows, even when BOMs share a raw material.
Native outgoing stock valuation determines the group's material cost. Finished
goods receive that cost through native **Set Basic Rate Manually**, plus only
their own extra packing charge through native Additional Costs. Additional
costs entered manually outside the BOM table retain the native proportional
allocation by finished-goods base value (quantity if all base values are zero).

For example, two BOM groups consuming AED 20 and AED 30 of materials and
carrying AED 2.50 and AED 5.00 of extra charges receive AED 22.50 and AED 35.00
of stock value respectively. The extra charges do not increase the remaining
bulk item's unit valuation. Outgoing stock reduces through the normal ledger.
Existing finished stock follows its configured valuation method.

Reposting uses updated outgoing values to recalculate the same group costs.
This feature does not write Item master buying/selling prices or Item Prices.

## Scope and validation

- Independent Repack entries only; no Work Order or Van Stock Entry.
- Active, submitted BOMs belonging to the entry's company.
- Positive output quantities and nonnegative extra packing charges.
- BOMs with scrap/process loss, including exploded sub-BOMs, require separate
  entries. A finished item cannot also be consumed in the same entry; use
  sequential entries for intermediate production.
- Raw-material actual quantities and batch splits may be adjusted within their
  BOM group. Finished quantities must still match the BOM table's Stock UOM
  quantity. Generated group references must remain intact.

Retail owns the controller subclass, client script, child DocType and custom
fields. Ordinary Stock Entries delegate to ERPNext. `retail.repack.install` runs
after schema sync and migration; no historical documents are rewritten.

## Verification

Run the database-free native-calculation regressions from the bench root:

```sh
env/bin/python -m unittest retail.tests.test_repack -v
```

`validation/repack_browser.py` checks unsaved forms on `retail-test.localhost`
using existing nesto demonstration BOMs. It creates and removes a temporary
Administrator session, and saves no Stock Entry. Chromium must have its system
libraries available. Browser screenshots are written under `/tmp`.

Unsaved preview and validation checks do not prove submitted Stock Ledger or
General Ledger results. No stock movements are submitted by these checks.

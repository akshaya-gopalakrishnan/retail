# Scrollable child tables

The scrollable layout is enabled for `items` in Purchase Order, Purchase Invoice,
Purchase Receipt, Material Request, Stock Reconciliation, Stock Entry, Delivery
Note, Sales Order, Sales Invoice, and POS Invoice. Native Frappe controls,
validation, calculations, permission checks and pagination remain responsible for
the document. No framework source or database schema is changed.

The gear menu selects and orders columns. Column widths automatically fit translated headings and formatted values on the
current page, between 64 and 320 pixels including control padding. Saved width
units remain stored for compatibility but do not set pixel widths in this layout. The table scrolls horizontally. Item and
row identifiers stick on desktop; narrow screens use normal touch scrolling.
Link suggestions are temporarily rendered outside the overflow container using
the same native dropdown and event handlers. Opening a row temporarily returns
the grid to viewport width for the standard expanded editor.

## Reuse

Register an additional parent/table pair in a loaded custom script:

```js
retail.scrollable_grid.register("Sales Invoice", "items", { pin_field: "item_code" });
```

`enable(frm, fieldname, options)` can also be called from a form refresh handler.
Each grid instance is wrapped once; global Grid and GridRow prototypes are not
modified. Noneditable template-rendered grids are intentionally skipped. Editable grids
with fallback templates (including PI Items) are enabled normally.

Preferences use the parent DocType's `RetailScrollableGrid` user setting, keyed
by table fieldname. Existing `GridView` preferences seed the first view but are
not overwritten. Reset to default clears only this table's trial selection and
shows its eligible `in_list_view` fields.

## Rollback

Remove the relevant `register("DocType", "items")` call from the utility's boot
function, then hard-refresh the browser. For complete removal, remove the two
scrollable-grid asset entries in `hooks.py`, clear the site cache, and refresh.
Standard `GridView` preferences remain available. No business data migration or
rollback is needed. Update the asset query versions when shipping later edits.

## Validation

Run `node --test apps/retail/retail/tests/test_scrollable_grid.cjs` from the bench.
These checks load the installed native Grid source and verify the width budget,
permission filtering, metadata, settings isolation, repeat initialization, and
dynamic column visibility. They do not replace browser or accounting tests.

Manual Purchase Invoice checks:

1. Hard-refresh; open a draft PI. Use the gear menu to add more than ten columns.
2. Scroll both directions; check header alignment, item identity, and Tab navigation.
3. Edit quantity, FOC, purchase rate and VAT fields; compare expected totals.
4. Toggle Update Selling Price; check conditional columns and read-only fields.
5. Search/select Item, UOM and Warehouse, including the last row of a short table.
6. Add, delete and reorder rows; test a table with enough rows for pagination.
7. Save the draft, reopen it, and check values and column preferences.
8. Open and close the expanded row editor; check a submitted PI remains protected.
9. Check a narrow screen and the active Arabic/RTL layout if used.
10. Check the registered transaction Items tables use the scrollable layout;
    PI's taxes table and unregistered tables should retain the standard layout.

## Durable column preferences

Retail's configured forms (listed explicitly in `column_preference_doctypes.json`)
now use `retail.column_preferences.save` for table column updates. Both standard
`GridView` tables and `RetailScrollableGrid` tables write to `__UserSettings` in
the POST request transaction. They no longer depend on the hourly Redis sync.
Cache clearing reloads the same layout from the database. The endpoint accepts
only these two column namespaces, checks parent read permission, validates the
parent/child relationship, and always uses the logged-in user.

The client attaches handlers only to table instances on the listed forms. It does
not replace Frappe's generic settings endpoint or global settings-save method.
When adding another Retail form, add its parent DocType to the explicit allowlist.
The scope includes forms configured in Retail hooks/navigation, custom Retail
forms with tables, and forms with Retail-shipped grid defaults. Standard list-view
configuration already saves its List View Settings document directly to the DB;
this change does not alter that separate UI or report definitions.

Migration default installation preserves saved selections, including explicit
null/empty resets. An administrator deliberately invoking an overwrite patch can
still change defaults. No business document data is changed.

Persistence tests:

- `node --test apps/retail/retail/tests/test_column_preferences.cjs`
- `retail.tests.test_column_preferences` (Frappe site context; synthetic settings
  identities and rolled-back database writes).

After loading the new Desk assets, use the gear menu to choose columns and click
Update. Reload, clear cache, and reopen the same form as the same user to verify
that the selected columns and order remain.

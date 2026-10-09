# Shared keyboard navigation

All rules live in `retail/public/js/retail_keyboard.js`, loaded once through
`app_include_js`. No per-DocType keyboard scripts are needed.

- Enter in a parent input commits it, then focuses the next visible, editable
  required control in form order. Dynamic `reqd` flags are respected. Optional
  fields remain reachable using normal Tab navigation.
- After the last required control, focus the form's Scan Barcode input. If it is
  unavailable, focus the first editable cell in Items (create an initial row if
  necessary and permitted).
- Enter inside an item input commits it and edits the next visible editable
  column in the displayed order. The last column inserts a row immediately below
  the active row. An item row without an item code does not create another row.
- Shift+Enter closes the current field's suggestions/calendar, commits the input,
  and focuses the form scanner. Empty required fields do not trap this shortcut;
  validation of entered values and document-save validation remain in place.
- All four arrows use rendered field positions. Left/Right only selects a field
  beside the current one in the same visual row; Up/Down only selects a field
  above/below with horizontal overlap. There is no side-to-next-row wrapping.
  Checkboxes, optional fields, required fields and rendered editable table cells
  participate; hidden/read-only controls are skipped. With no candidate in the
  requested direction, focus stays put. Empty Items tables can receive their
  initial row. Arrow navigation does not enforce empty-required checks.
- Enter on a focused checkbox toggles it through its native click/change handler
  and keeps focus there. A second Enter reverses it. Holding Enter does not toggle
  repeatedly. Shift+Enter retains its scanner shortcut.
- Escape exits inline editing into cell selection.
- Tab and Shift+Tab are native, as are open dropdowns, multiline Enter, dialogs,
  date pickers, save shortcuts, and button actions. Enter has no automatic
  document-save or submit action.
- Focus changes reveal the target instantly using nearest scrolling. Sticky Desk
  headers and pinned item columns are kept clear. This includes native Tab; manual
  scrolling is not followed or undone until focus changes again.
- Manual Enter, arrows, Shift+Enter and row insertion have no fixed quiet-period
  delay. They await the specific control validation; unrelated background requests
  do not delay focus. A control already validating is allowed to finish before the
  latest input is committed.
- Native scanner Enter runs once; focus returns to the scanner after processing.
  New keyboard/pointer activity or route changes cancel pending focus movement.

Existing central configuration remains supported:

```js
retail.keyboard.doctypes["My Document"] = {
  scan_field: "custom_scan_barcode",
  items_field: "items"
};
retail.keyboard.children["My Item"] = {
  first_field: "item_code",
  skip: ["custom_internal_field"]
};
```

Either configuration accepts `enabled: false`. `scan_field: false` disables scan
lookup. Default scanner fieldnames are `scan_barcode`, `barcode`, `item_barcode`.
Custom scanners can supply `when_scan_complete(frm)` returning a promise.

Run `node --test apps/retail/retail/tests/test_retail_keyboard.cjs` from the bench.
The tests isolate DOM/server services; they do not replace manual browser checks
with real dropdowns and a physical barcode scanner.

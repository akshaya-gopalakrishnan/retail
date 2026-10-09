# POS list filters and columns

Edit `retail/pos_list_settings.py` in the retail app:

- `FILTERS`: field names shown in the top filter bar, grouped by DocType.
- `COLUMNS`: default list columns, grouped by DocType. `status_field` is the status badge.
- `configure()`: custom display field definitions and property setters.

Apply filter/column changes with:

```sh
bench --site SITE execute retail.pos_list_settings.configure
```

Then reload the browser. Migration also applies this configuration. Other fields remain accessible through the Filter dialog. Use internal field names, not labels. The general pattern for other DocTypes is their DocType JSON `in_standard_filter`, or a Property Setter for core ERPNext fields.

`retail/public/js/list/pos_master_status.js` controls Active/Inactive badges for POS Profile (`disabled`) and POS Branch Counter (`is_active`). “POS Counters” is the navigation label for POS Branch Counter.

`retail/pos_list_settings.py` also maintains:

- Sync Posting Date: payload business date, then posting date, then log creation date.
- Counter: a Link to POS Branch Counter, resolved from counter code and branch. Ambiguous/unmatched historical codes are left blank; original Counter Code is retained.
- Opening Cash: sum of opening balances whose Mode of Payment has type Cash.
- Closing Amount: sum of actual closing balances across all payment methods.
- Opening Period End Date: date of the submitted closing entry; blank for an open session. Cancelling the closing clears it when no submitted closing remains.

The one-time patch `retail.pos_list_settings.execute` backfills these display fields on existing records. It does not delete historical logs or modify their operation keys, requests, or responses.

`retail/api/pos_sync.py` (`_run`) returns the success receipt from `retail/pos_operations.py` directly, avoiding a second success log. Failed attempts continue to be logged separately.

# Retail ownership of former core customizations

Implemented 2026-10-15 for ERPNext 15.108.3 / Frappe 15.108.0.

- `core_compat.reports.RetailReport` extends the native Report controller. Accounts
  Receivable, Accounts Payable, their summaries, and Gross Profit execute Retail
  implementations. Other reports delegate to Frappe. Native permissions, report
  names, routes, exports and prepared-report execution remain in Frappe.
- `core_compat.reports.get_script` delegates to the native permission-checked script
  endpoint, replacing only the two detailed account report scripts.
- The report implementations are snapshots of the previously modified ERPNext
  modules, with upstream copyright headers retained. This deliberately preserves
  the existing calculation and allocation behavior. Review these snapshots when
  upgrading ERPNext; they do not automatically inherit upstream report changes.
- `core_compat.runtime.install` wraps ERPNext's internal `insert_item_price` once.
  Frappe v15 has no hook around that helper. The adapter checks installed apps for
  the current site and skips only Sales Invoice / POS Invoice writes, exactly as
  the former source edit did. Other documents and non-Retail sites delegate.
  HTTP and worker hooks install the adapter; the existing invoice controllers and
  item-detail API also install it for direct document/API operations.
- `core_compat.setup.install` installs three Item Property Setters and adds license
  shortcuts to the Users workspace. It writes workspace metadata without saving
  a standard workspace through developer-mode export, keeping Frappe source clean.
- Sales Invoice - Copy belongs to Retail-app. Its current saved layout is shipped
  in the Retail fixture and as a missing-record fallback. The old untracked core
  export differed from the saved layout and is archived, not installed over it.
- Item Python typing-only edits were reverted without replacement.

Setup runs after sync and migration and is idempotent. Run only the narrow setup
on an existing development site with:

```
bench --site retail-test.localhost execute retail.core_compat.setup.install
bench --site retail-test.localhost clear-cache
```

Pre-cleanup core diffs and the old untracked export are preserved under
`validation/core-cleanup-2026-10-15/`.

Verified on retail-test.localhost: all five report executions; saved Item metadata;
workspace shortcuts; setup idempotency; print HTML preservation; six regression
tests; authenticated HTTP 200 for report JavaScript, Item metadata and the native
Desk report page. No browser visual interaction test was available.

# Desk speed changes — 2026-11-27

Applied to the Retail app and checked on `retail-test.localhost`. No production deployment or business-data migration was performed.

Implemented concurrent metadata-request deduplication (including failure/retry and native synchronous callers), preloaded widget definitions on all ten named Retail workspaces, shared card requests using saved native card definitions, and chart rendering with preloaded field formatting. Native chart filter controls load metadata only when opened. No global metadata skip list is used.

Dashboard values and customer balances cache for 60 seconds; workspace responses cache for 300 seconds. Cache identities include user, company, date, language and arguments. Card authorization runs before cache lookup; customer input and permission checks remain before its cache. Committed accounting, stock, master-data and permission changes invalidate related caches. Transaction callbacks coalesce, rolled-back writes do not invalidate, and epochs prevent in-flight requests from restoring obsolete cache entries. Clear-cache also invalidates these caches.

Document-code checks run in the background once per DocType, retry after failures, and use an hourly server completeness flag. Server form metadata has an hourly warmup. The User permission editor loads its authorized registry on demand instead of duplicating it in boot.

Stock Ledger now requires an item, item group, warehouse, voucher, barcode, batch or serial filter. It explicitly warns when only the first 500 rows are returned; narrow the filters for a complete ledger. Its existing stock calculations, barcode handling and result metadata are preserved. Other reports have no new row cap.

## Verification

- 30 focused Python regression checks passed, plus JavaScript checks for metadata deduplication, widget preloading, card batching and chart rendering.
- Real Chromium checks: no JavaScript exceptions or API failures; no transaction metadata requests while opening the seven tested workspaces; one metadata request on each tested list; no per-widget `load.getdoc` requests. Native chart filters still opened, and the User permission editor rendered 96 checkboxes.
- Three simultaneous Payment Entry metadata callers made one request and all received metadata.
- A normal existing cashier's 137-workspace boot list matched the live permission-filtered sidebar endpoint.
- A disposable MariaDB/Redis clone proved real invoice submission added 17 to cached sales, and cancellation restored the original totals. Native card results matched the original Frappe methods. Only the unrelated backend password-approval guard was mocked in this fixture; native invoice calculations, submission and cancellation hooks ran. No source-site test invoices were created. The cached card request took 3.79 ms in this isolated check.
- The actual Stock Ledger report controller returned no rows and a filter prompt for an unfiltered request.
- `bench doctor` reported one background worker online. This development check does not establish production Gunicorn configuration.

Measured SPA route-to-network-quiet estimates, excluding the harness's final 800 ms idle-confirmation period:

| Page | Local measured time | Metadata requests |
|---|---:|---:|
| Items workspace | 493 ms | 0 |
| Sales workspace | 279 ms | 0 |
| Stocks workspace | 325 ms | 0 |
| POS workspace | 276 ms | 0 |
| Accounts workspace | 351 ms | 0 |
| Reports workspace | 129 ms | 0 |
| Business Home reopening | 113 ms | 0 |
| Item list | 406 ms | 1 |
| Customer list | 285 ms | 1 |
| Purchase Invoice list | 481 ms | 1 |
| POS Invoice list | 407 ms | 1 |

A repeated desktop API request returned in 9 ms (10 preloaded definitions). The Purchase Invoice list did not request Purchase Receipt metadata. The local boot was approximately 360 KB after removing the duplicated editor registry; the document's under-303-KB target is not achieved. The sidebar/report permission data required by current features remains intact.

These local timings are not before/after measurements against the report's larger production dataset. The browser harness uses an ephemeral local HTTP server without Socket.IO; its socket polling 404s are expected and excluded from API failures.

## Proposals intentionally deferred

No scale fields were deleted or invoice-item fields moved to a new DocType: existing code and POS contracts still use them, and their migration needs separate compatibility and historical-data validation. No accounting/profit formula was replaced with a simplified aggregate SQL. No speculative indexes, production worker changes, broad report caps, permission/report-registry trimming, or removal of theme/telephony assets was applied.

## Deployment

Source and built assets are local. For another site, deploy the Retail source and build assets, clear that site's cache, and run `bench --site <site> execute retail.desk_speed.warmup_meta`. Restart the appropriate application services for that deployment. Recheck real user permissions, transaction invalidation and browser timings on the target dataset. No schema migration is required by these changes.

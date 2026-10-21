# Phase 1 sidebar validation

Site: retail-test.localhost. All nine cases returned identical complete sidebar payloads before/after, cold/warm. Live accounts were used for Administrator, Celesta Super Administrator, Customer Administrator and Driver/Van. Other cases use the existing Retail role presets via temporary in-process role overrides; no user records were changed. Restricted-module case temporarily blocks Stock and Buying.

Cold means a full Frappe site cache clear before execution. Warm means a new Frappe context using populated shared caches. SQL counts count frappe.db.sql invocations including metadata/permission initialization. One observation per cell; latency is noisy and is not a statistical speedup claim. These cold measurements are not directly comparable with the supplied 1,226-query audit.

| Case | Cold ms before → after | Cold SQL before → after | Warm ms before → after | Warm SQL before → after |
|---|---:|---:|---:|---:|
| Administrator | 4495.07 → 4463.34 | 3535 → 3490 | 119.13 → 123.98 | 41 → 5 |
| Celesta Super Administrator | 5613.28 → 7097.97 | 3814 → 3775 | 315.71 → 233.34 | 144 → 108 |
| Customer Administrator | 4336.65 → 4314.66 | 3029 → 3015 | 882.37 → 1216.79 | 249 → 237 |
| Store Manager preset | 3819.17 → 4033.21 | 3414 → 3390 | 577.46 → 555.88 | 325 → 301 |
| restricted module preset | 4270.65 → 4243.82 | 3266 → 3248 | 660.14 → 484.08 | 275 → 257 |
| Driver/Van live | 4079.04 → 4897.45 | 3315 → 3300 | 684.63 → 692.55 | 310 → 296 |
| Van Sales User preset | 3203.18 → 3226.32 | 3076 → 3072 | 356.29 → 334.67 | 231 → 227 |
| Cashier preset | 3643.94 → 3241.58 | 3133 → 3119 | 378.03 → 349.3 | 257 → 243 |
| Normal User preset | 3447.87 → 3042.47 | 2996 → 2996 | 327.66 → 367.65 | 231 → 231 |

## Cache boundaries and invalidation

- Discovery dictionary belongs to one _filter_workspace_sidebar_items call and is keyed by module; deep copies prevent workspace mutation leaking between content builds. All original item permission checks run for every workspace. No cached discovery survives the operation, including exceptions.
- No cross-request server final-result cache was added. User/role/module/report/workspace changes cannot leave a Retail server result stale. Existing Frappe cache lifecycle remains in force.
- Browser uses Retail-filtered boot pages for initial mounting only, shares pending calls, and reuses results within a route. Router changes clear resolved/pending references and increment a generation; responses from old routes cannot refill the cache or mount stale sidebars. Like existing mounted Desk navigation, live permission/configuration edits in another session require navigation/reload; this change does not implement realtime permission broadcasts.
- Observer remains active; initial and mobile refresh passes are coalesced. Missing mount sections retain an eight-attempt fallback with at most one pending timer.

## Validation and limits

- Eight Python tests passed: existing report hierarchy/visibility tests plus discovery lifetime, module separation, mutation isolation, and per-workspace permission rechecks.
- Navigation Node tests and JavaScript syntax check passed, including filtered boot reuse, fallback request sharing, stale route response rejection, Driver and Sales Invoice navigation.
- Administrator warm discovery queries: 38 → 2 (19 identical of each type → one each). Total warm SQL: 41 → 5.
- No browser LCP/visual measurement was performed. POS transaction, licensing and report execution were not retested end to end; their source was unchanged by this phase.
- Retail SidebarWorkspace.get_links mirrors the current Frappe method and should be checked against upstream when upgrading Frappe.
- Cold latency has no consistent improvement; Super Admin and Driver cold calls were slower in this sample. Remaining permission/metadata/content work dominates completely cold calls.

Reproduce from sites with ../env/bin/python ../apps/retail/validation/sidebar_phase1/measure.py /path/to/pre-change/workspace_permissions.py. This intentionally clears development site caches and rolls back DB transactions. Raw results are in results.json.

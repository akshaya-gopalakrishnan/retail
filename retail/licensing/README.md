# Offline-safe customer license client

Open `/app/celesta-license-settings` as Retail `Super Admin` or the built-in
Administrator recovery user. Save the key to generate the installation UUID,
assign that UUID on the central server, then Activate and assign licensed users.

Deployment configuration (provision through a trusted deployment channel):

- `celesta_license_server_url`: central HTTPS origin.
- `celesta_license_public_keys`: standard-base64 raw 32-byte Ed25519 public keys.
  Multiple pinned keys support rotation. Never install the signing private key here.

The central activate/verify endpoint must return `message.token`, a signed EdDSA
JWT with `kid` equal to the first 16 hex characters of SHA-256 of the raw public
key. Claims bind `iss=celesta_license`, `aud=celesta_retail`, `sub=installation UUID`,
`license_id`, positive integer `license_version`, integer `iat`, `nbf=iat`, `exp`, and `rules`. See signature.py for the
validated rules schema. Only signed rules supply license authority.

Login and authenticated requests verify the stored token locally, without HTTP.
Normal users need a selected seat within the signed allowed-user limit. Editable
status, user limits, verification dates and offline deadline fields cannot grant
access. The token signature, installation binding, active status and signed `exp`
are checked again before granting access. `expiry_date` is display/reporting metadata
on retail; it never supplies an additional local-calendar authorization cutoff.

The hourly scheduler calls central verify using bounded HTTPS requests. Enable the
site scheduler/workers and synchronize scheduled jobs after deploying the retail
hooks change (normally during migration). Manual Sync/Verify is also available.
Network, HTTP or invalid-response failures preserve the previous signed token;
billing continues while it remains locally valid. Failures never reset grace.
The deadline cannot exceed `iat + offline_grace_days * 86400`; access stops at
`exp`. The central server folds its calendar expiry into signed `exp`. Active licenses require at least one grace day. A verified signed revocation/suspension replaces the old token
and blocks normal users immediately on their next request.

Missing, tampered, expired or suspended local licenses fail closed for normal users.
Administrator is the only full emergency recovery account. Retail Super Admin
(the `Super Admin` role) can authenticate for restricted licensing repair while the
license is invalid. `/app` redirects to `/app/celesta-license-settings`, which serves
a small recovery form without loading Desk or business data. Existing Retail access
controls protect the Super Admin role. A valid license immediately restores ordinary
seat enforcement for Super Admin too, including settings access.
Changing the license key clears the cached token. Ordinary form saves cannot edit
verified metadata. Seat removals remain possible during recovery.

Keep server time and deployment configuration protected: this cannot defend
against an operator controlling the application code, database, clock and pinned
keys together. No secrets or central response contents are logged by refreshes.
Max Devices, Max Sessions/User and Device Restriction are labelled **Not enforced yet**. They are signed metadata only; no device/session enforcement is implemented.

Tests (from the bench directory):

```sh
env/bin/python -m unittest discover -s apps/retail/retail/licensing -p "test_*.py" -v
```

## Protected rollback state and deployment

### Separate licensing and POS endpoints

The HTTPS origin configured in `celesta_license_server_url` must route to the
site running `celesta_license`, not to the Retail site. The .NET POS base URL
routes to Retail. For temporary ngrok hosting, use separate HTTPS endpoints and
rewrite each upstream Host header to its intended Frappe site. On this bench,
the licensing upstream is `license.localhost:8000` and the Retail upstream is
`retail-test.localhost:8000`. Production uses its own site names. Do not copy a
development ngrok origin into production without verifying its routing.

Keep the license server and tunnel running and the configured origin stable.
When moving the authority to a hosted server, update the configured origin and
retain its license records, installation bindings and signing key. No POS URL
or login enforcement change is needed for that move. Verify a fresh signed
response after switching. Never ship the authority's private signing key to Retail.

Refresh diagnostics distinguish routing, connectivity, HTTP rejection, malformed
responses, protected-state problems and signed-token validation failures using
fixed messages. They never display or log raw server responses or credentials.
Hourly failures retain the previous token and log the safe diagnostic. If its
authenticated signed deadline is within six hours or already passed, the job
creates a daily Notification Log alert for enabled Administrator/Super Admin
users, with separate near-expiry and expired alerts. Normal Frappe notification
preferences control email delivery. An unavailable scheduler/worker cannot
generate these alerts, so deployment must also monitor those services.

The subscription expiry date and signed token deadline are different: a valid
subscription still needs periodic refresh before the token's offline deadline.
Failures never extend that deadline. Existing sessions keep the current login-time
enforcement behavior; new normal-user logins require a locally valid token and
an assigned seat.

Manually configure `celesta_license_state_path` as an absolute server-only path,
for example `/var/lib/celesta/retail-test/license-state.json`. The client rejects paths that resolve inside the bench sites directory, including
symlink aliases. Deployment must first create its parent directory owned by the bench
service user with mode exactly 0700; state
and lock files use 0600. Keep this path outside site files, database backups and
customer-controlled restore procedures. All web/worker processes for an installation
must share this persistent state and support POSIX file locking and atomic rename.
The licensing implementation never edits site configuration. The operator must also
exclude this directory from any external database-restore or site-backup automation;
the client cannot detect arbitrary backup destinations. A shared persistent volume
is required when web and workers run in separate containers.

Activate/Verify as Administrator or a restricted recovery Super Admin initializes missing state from a fresh signed
central response. Offline access cannot initialize state. The file preserves the
installation binding, highest license version, highest accepted `iat`, highest trusted
time and token hash, without credentials. Corrupt/unreadable state or a changed
installation fails closed. Preserve this file across deployments/restarts and database
restores; do not reset it to make an old backup work. Correct server time and fetch a
fresh token to recover. An intentional installation transfer requires operator-managed
state provisioning and a fresh central binding; do not reuse the previous installation's
state file.

Both live and offline checks reject lower versions or lower issued times. Signed
inactive responses advance the floor too. Every successful authorization advances
trusted time. Clock rollback over 60 seconds fails closed; within that tolerance,
authorization uses the highest trusted time, so time and expiry never move backwards.
Atomic writes, fsync and a process lock preserve floors across restarts/concurrent
requests. A protected-state write can survive a rolled-back database transaction;
recover with a fresh verification, never by lowering the floor.

An operator controlling application code and protected OS state can bypass licensing.
This is rollback protection against ordinary database restore/customer document edits,
not tamper-proof protection. Offline revocation still takes effect only on successful
synchronization or the signed deadline. No device/session enforcement was added.

The existing `scheduler_events["hourly"]` hook registers
`retail.licensing.client.scheduled_sync` through Frappe's migration job synchronization.
For this site, verify the row and runtime health with:

```sh
bench --site retail-test.localhost execute frappe.client.get_list --kwargs '{"doctype":"Scheduled Job Type","filters":{"method":"retail.licensing.client.scheduled_sync"},"fields":["name","frequency","stopped"]}'
bench --site retail-test.localhost doctor
```

Expect one Hourly job, `stopped=0`, an enabled scheduler and available workers.
Normal deployment migrations synchronize hooks. To register only this job without
migrating unrelated apps, use:

```sh
bench --site retail-test.localhost execute frappe.core.doctype.scheduled_job_type.scheduled_job_type.insert_single_event --kwargs '{"frequency":"Hourly","event":"retail.licensing.client.scheduled_sync"}'
```

After reviewing deployment settings, the operator can enable the scheduler using
`bench --site retail-test.localhost enable-scheduler` and start/restart scheduler,
web and worker processes through the deployment's process manager. Verify a successful
Scheduled Job Log and advancing license verification time after central configuration.
Central schema migration must happen on the actual central deployment; the active
retail test site does not have the central app installed. Coordinate rollout: old tokens
without `license_version` fail closed until a new central response is accepted.

## Deployment file inventory (2026-10-01)

These are the modified/untracked licensing files and existing dependencies that must
be included in a reviewed deployment commit. `M` means modified, `??` untracked;
paths are relative to the indicated app. Existing Registered Device metadata is
included for completeness; device/session enforcement remains unimplemented.
`pyproject.toml`, `retail/hooks.py`, access control and existing settings/seat DocTypes
were already changed/untracked before this audit fix; they remain required. The retail
hooks file also contains unrelated changes: stage/review licensing hunks carefully.
No commit or push was performed.

`apps/celesta_license`:

```text
 M README.md
 M celesta_license/hooks.py
 M pyproject.toml
?? celesta_license/api.py
?? celesta_license/celesta_license/doctype/__init__.py
?? celesta_license/celesta_license/doctype/customer_license/__init__.py
?? celesta_license/celesta_license/doctype/customer_license/customer_license.js
?? celesta_license/celesta_license/doctype/customer_license/customer_license.json
?? celesta_license/celesta_license/doctype/customer_license/customer_license.py
?? celesta_license/celesta_license/doctype/license_history/__init__.py
?? celesta_license/celesta_license/doctype/license_history/license_history.json
?? celesta_license/celesta_license/doctype/license_history/license_history.py
?? celesta_license/celesta_license/doctype/registered_device/__init__.py
?? celesta_license/celesta_license/doctype/registered_device/registered_device.json
?? celesta_license/celesta_license/doctype/registered_device/registered_device.py
?? celesta_license/migration.py
?? celesta_license/tests/test_api.py
?? celesta_license/tests/test_customer_license.py
```

`apps/retail`:

```text
 M retail/hooks.py
?? retail/access_control.py
?? retail/access_defaults.py
?? retail/test_access_control.py
?? retail/public/js/forms/access_control.js
?? retail/docs/access_control.md
?? retail/licensing/README.md
?? retail/licensing/__init__.py
?? retail/licensing/client.py
?? retail/licensing/enforcement.py
?? retail/licensing/signature.py
?? retail/licensing/state.py
?? retail/licensing/test_client.py
?? retail/licensing/test_enforcement.py
?? retail/licensing/test_scheduled_sync.py
?? retail/licensing/test_signature.py
?? retail/licensing/test_state.py
?? retail/retail_app/doctype/celesta_license_settings/__init__.py
?? retail/retail_app/doctype/celesta_license_settings/celesta_license_settings.js
?? retail/retail_app/doctype/celesta_license_settings/celesta_license_settings.json
?? retail/retail_app/doctype/celesta_license_settings/celesta_license_settings.py
?? retail/retail_app/doctype/celesta_licensed_user/__init__.py
?? retail/retail_app/doctype/celesta_licensed_user/celesta_licensed_user.json
?? retail/retail_app/doctype/celesta_licensed_user/celesta_licensed_user.py
```

Separate pre-existing ERPNext core deployment/upgrade blocker (untouched; paths
relative to `apps/erpnext`):

```text
 M erpnext/accounts/report/accounts_payable/accounts_payable.js
 M erpnext/accounts/report/accounts_receivable/accounts_receivable.js
 M erpnext/accounts/report/accounts_receivable/accounts_receivable.py
 M erpnext/accounts/report/gross_profit/gross_profit.py
 M erpnext/stock/doctype/item/item.json
 M erpnext/stock/doctype/item/item.py
 M erpnext/stock/get_item_details.py
?? erpnext/accounts/print_format/sales_invoice___copy/__init__.py
?? erpnext/accounts/print_format/sales_invoice___copy/sales_invoice___copy.json
```

## Deployment validation, 2026-10-01 (completed checks)

The dedicated central `license.localhost` site was explicitly approved for development
validation. It migrated successfully with only Frappe and celesta_license installed.
No retail/ERPNext migration was run. Frappe source remained clean; the unrelated
ERPNext changes listed above remain a separate deployment/upgrade blocker.

The state-path check now rejects paths inside the sites tree (including symlink
aliases) and requires an owner-only 0700 parent. Unit coverage includes this boundary.
The licensing hooks remain together at the end of `retail/hooks.py`; no unrelated
hook hunks were moved or staged. `retail/access_defaults.py` is also required by
`retail/access_control.py` installation and must accompany that existing dependency.
Frappe currently supplies cryptography and requests; central additionally declares
its cryptography dependency explicitly.

Validation performed:

- 18 central unit tests passed. Real central database checks verified schema,
  generation/regeneration, versions, grace validation, history immutability and
  permissions, legacy migration/idempotence, and no plaintext in document/list/CSV
  export. Test writes were rolled back or the exact fixture explicitly removed
  after Frappe export audit logging committed it.
- 20 retail unit tests passed, including the added path regression. The three existing
  initialized-site integration tests also passed with database rollback. Their mocked
  central response is separate from the real HTTPS checks below.
- Real TLS-verified HTTPS Activate and Sync/Verify ran between `license.localhost`
  and `retail-test.localhost`, with a generated development Ed25519 seed, pinned raw
  public key, matching installation UUID, test Customer License and two real test
  users (Stock User and Super Admin). Token storage, signed version, SHA-256-derived
  kid, 0600 state/lock permissions and central-only private-key configuration passed.
- Redis Queue/Cache were stopped; starting the existing `config/redis_queue.conf`
  and `config/redis_cache.conf` services resolved connectivity without configuration
  changes. The retail scheduler was enabled. Exactly one Hourly licensing job had
  `stopped=0`. Its normal Scheduled Job Type enqueue/execution path ran through an
  actual RQ burst worker, produced a Complete Scheduled Job Log, and advanced
  `last_verified` after real central verification. This was an explicitly enqueued
  scheduled job, not a wait for the hourly timer. The earlier unactivated no-op run
  alone was not treated as successful verification. Burst workers exited afterward;
  a continuously managed scheduler/worker is still required for deployment.
- The central HTTPS process was stopped while retail HTTPS, Redis and MariaDB stayed
  available. Fresh normal/Super Admin logins and authenticated requests succeeded.
  The normal Stock User inserted a real draft Purchase Material Request using an
  existing item/warehouse/company through `frappe.client.insert`; the insert was
  rolled back and absence verified. An HTTP-call tripwire around authorization and
  transaction execution stayed silent. Failed central sync preserved the exact
  cached token, issued time and offline deadline.
- Fresh signed suspension/revocation blocked both user roles, including real HTTP
  login denials for suspension. Reduced allowed_users excluded the second assigned
  seat; removing a seat blocked its user. Tampered signatures and an actual signed
  Active token evaluated past exp blocked both roles. Built-in Administrator retained
  recovery, and fresh central verification recovered service.
- Database rollback used an actual snapshot/restore of the licensing `tabSingles`
  rows: accept N, sync N+1 suspension, restore N rows, and reject the restored token.
  The protected file remained byte-for-byte unchanged by the database restore.
  No protected floor was weakened/reset. This was a scoped licensing-data restore,
  not a destructive full ERP database restore.
- Clock checks used injected licensing verification times, not changes to the host
  clock: normal time, a tolerated 30-second rollback, and a rejected 61-second
  rollback. A new Python process read the same persistent floor and rejected rollback;
  a fresh real central verification at correct time recovered. No floor was reset.
- The regenerated old credential was rejected by the real central HTTPS API; its
  replacement activated through retail. The API returned `Cache-Control: no-store`.
- Rotation used a second real central Ed25519 key with both public keys pinned;
  old and new tokens verified and the new kid matched its public key's SHA-256 prefix.
- All tracked and untracked files in both apps were scanned for the generated
  plaintext license keys and private Ed25519 seeds: no matches. Nothing was staged.
  Tracked files also contained no private-key PEM or protected-state JSON artifact.
  No commit or push was performed.

Temporary test configuration used a private directory under
`/tmp/celesta-readiness-20261001/` and loopback HTTPS ports 18443/18444. Each independent
fixture used a distinct installation/state file; existing floors were preserved.
The harness and redacted results are in that directory for local review. This is
strictly a temporary development path, never a selected production state path.
All 16 end-to-end check groups passed. Test servers were stopped, the temporary TLS
private key destroyed, and original central/retail licensing configuration restored;
test users, seats and Customer Licenses removed; transaction writes rolled back.
The central migration and enabled retail scheduler remain. Do not rely on these
cleaned-up fixtures as a deployed customer license.

Production still requires an approved dedicated HTTPS central origin, securely
provisioned persistent signing seed, securely distributed public pins, an approved
persistent state directory outside backups shared by every retail process, customer
license provisioning/seat assignment, and managed web/scheduler/worker services.
After provisioning, repeat activation and verify an advancing timestamp through the
managed scheduler. Preserve protected state across releases and DB restores; correct
clock errors and verify online as built-in Administrator for recovery. Production
secrets and paths were deliberately not selected by this development validation.


## Restricted recovery follow-up, 2026-10-01

The earlier 16-group readiness evidence above is preserved. Its historical Super
Admin login-denial result is superseded only by the restricted recovery behavior
verified here; normal business operations remain blocked under the same denials.

The recovery request allowlist is exact:

| Request | Permitted while invalid for Retail Super Admin |
| --- | --- |
| GET `/app/celesta-license-settings` | Licensing-only form; no Desk boot |
| GET `/app` | Redirect to the recovery form |
| POST `/api/method/login` | Authentication and recovery landing URL |
| GET/POST `/api/method/retail.licensing.enforcement.recovery_settings` | Read installation/status/seat names; save key, generate the installation UUID, remove/reassign seats |
| POST `/api/method/retail.licensing.client.activate` | Activate |
| POST `/api/method/retail.licensing.client.verify` | Sync/Verify |
| POST `/api/method/logout` | Logout |

Legacy root `cmd=login/logout` POSTs are also supported. Mismatched command
parameters, path suffixes, generic document read/save/insert/set-value APIs, reports,
method runners, business pages, private files and v1/v2 API aliases are denied.
The recovery form accepts only a key and exact user names; it cannot edit arbitrary
DocTypes, verified metadata, server configuration, roles or permissions. Installation
UUID handling is unchanged. Central URL, public pins and state-path configuration
remain deployment-operator tasks, never browser-editable secrets/configuration.
Seat edits while invalid are staged assignments, not authorization. Only enabled,
non-Guest/non-Administrator users can be newly assigned. Duplicate rows are rejected.
Once valid, the signed allowance and ordered assigned seats determine access for
Super Admin too. Put the recovery account within that allowance before activation;
if it is unseated after restoration, Administrator must repair its seat assignment.

Validation: 22 retail unit tests and 18 central unit tests passed. All four initialized
`retail.licensing.test_client` tests passed on `retail-test.localhost`, including real
DB users, password authentication, signed missing/tampered/expired/suspended/revoked
and elapsed-deadline cases, actual whitelisted Activate/Verify and settings dispatch,
seat removal/reassignment, exact request-guard denials and restoration of seat
limits. Central HTTP responses in this follow-up integration test are mocked; the
real TLS evidence above remains the earlier run. Integration fixtures use temporary
protected state and database rollback, without permanent provisioning. The recovery
form JavaScript passed `node --check`. Only the Retail settings DocType metadata
was reloaded on the active site to apply the help text; no core migration ran.

The active `retail-test.localhost` was intentionally cleaned after readiness tests:
**no central URL, no public pins, no state path, no installation activation, and no
seats**. This is a deployment state, not a code defect. Do not auto-provision permanent
secrets or configuration to make the cleaned development site appear licensed.

The deployment inventory above was rechecked against full modified/untracked Git
status. Central's only supporting change in this follow-up is the Customer License
metadata help text. Retail's changes are enforcement, its existing two test files,
Celesta License Settings metadata and this README. No dependency was added: deploy
central `pyproject.toml` (cryptography), Retail licensing/access-control hooks and
`access_defaults.py` plus the existing access-control tests/UI/docs listed above;
Frappe's existing `pyproject.toml` supplies requests and cryptography. No secret,
private-key or protected-state artifact is tracked. Nothing was staged, committed
or pushed. Frappe core is clean; the listed unrelated ERPNext edits remain untouched.

Deployment still needs metadata synchronization for both settings forms, reviewed
app files/dependencies, managed services, and the production configuration/provisioning
steps above. Do not run or revert unrelated ERPNext migrations/changes as part of
this licensing fix.


## Remaining foundation audit fixes, 2026-10-01

Protected state binds the current `license_id`, its version floor, the monotonic
issued/time floors and any previously retired identities. Renewal and key regeneration
must use the existing Customer License row and installation UUID. The central schema
requires a unique `installation_id`; do not create a second row for that installation
or move the binding away from the existing row. Change expiry/status/entitlements on
the existing row, or use Regenerate Key, then save the new key in retail and Activate.
These operations increment the existing identity's version. Saving a key clears only
cached database metadata, never protected state. Online and offline identity changes
are rejected, including legacy signed transitions. No floor is reset. Existing protected
files, including retired identities from older releases, remain intact.

Legacy protected files acquire their identity only from the exact signed token
matching their saved `last_token_hash`; existing version/time floors still apply.
Verify that cached token locally before the first online refresh after upgrading.
If the database no longer has that exact token, recover the previously accepted
token from a trusted backup; do not delete or reset the protected file to bypass it.

Authentic expired, inactive and not-yet-valid tokens durably advance the protected
floors before offline denial. Invalid signatures, untrusted keys, malformed claims,
wrong installation/identity and rollback tokens cannot advance them. A subsequent
clock rollback cannot revive an expired token. Retail expiry authorization uses
only signed `exp`; the central issuer remains responsible for converting dates.

Administrator retains unrestricted recovery. Retail Super Admin receives restricted
recovery only while licensing is invalid; a valid license without an effective seat
still blocks Super Admin, and Administrator must repair the assignment. Ensure the
recovery Super Admin is included within the licensed seat allowance before activation.
No device restriction or session enforcement was added.

Validation: 46 licensing unit tests passed (27 retail, 19 central), plus all five
initialized-site tests on `retail-test.localhost`. That historical integration test accepted
replacement version 1 after version 5 using a mocked central response; it did not
validate the unique central installation constraint and is superseded by the
same-identity renewal regression below. Central HTTP responses are
mocked in site tests; central signature/binding behavior is separately unit tested.
Existing recovery tests and hourly registration passed. No new live HTTPS or managed
hourly timer run is claimed. Test fixtures use temporary protected files and database
rollback. Existing Git diff whitespace checks passed; Frappe core remains unchanged.

The modified/untracked deployment inventory above remains required, including the
central API/tests, retail licensing files/tests, hooks, DocTypes, dependencies and
access-control support files. This pass changed retail licensing `client.py`,
`state.py`, `signature.py`, `enforcement.py`, `test_state.py`, `test_client.py`,
`test_enforcement.py`, this README, and central `api.py` / `tests/test_api.py`.
Tracked-file inspection found no plaintext license credential, signing private key,
or protected-state artifact. Nothing was staged, committed or pushed.

The intentionally cleaned active dev site remains unprovisioned. Production still
requires the central HTTPS URL, securely provisioned central signing seed, retail
public-key pins, protected-state path outside backups, installation/license binding,
licensed seats, metadata synchronization, and continuously managed scheduler/workers.
Preserve protected state through every deployment and database restore. The existing
hourly hook is unchanged; validate activation and an advancing scheduled refresh
after production provisioning. The unrelated ERPNext upgrade blockers listed above
remain untouched.


## Unique installation renewal correction

The audit found that the earlier replacement API required two Customer License rows
with the same unique installation ID. No new identity is required for the supported
renewal or credential-regeneration workflows. Central now refuses a mismatched current
identity, and retail refuses even a signed identity switch without changing protected
state. No schema constraint was removed and no existing identity or floor was migrated.
The regression suite covers same-row renewal/key regeneration, rejection of identity
switches, unchanged floors on key saves, and restored-old-token denial after renewal.
Recovery and hourly hooks are unchanged. Device/session enforcement remains deferred.

Validation for this correction: 21 central and 28 retail isolated tests passed;
all five initialized-site tests passed on `retail-test.localhost`, with temporary
protected files and database rollback. Central database/request boundaries are
mocked; no new central-site database or live HTTPS test is claimed. The schema
regression checks the actual required/unique installation field definition. Recovery,
seat limits, signed-exp-only cutoff, offline authorization, key-save floor retention,
identity-switch rejection and old-token rejection after DB restore are covered.
Frappe remained clean and the pre-existing ERPNext modifications were untouched.

Runtime audit: the Hourly job is registered once with `stopped=0`; the site scheduler
setting is enabled, but no scheduler process was running and doctor reported zero
workers. The active development site intentionally has no installation/token, central
URL, public pins or protected state path. This is deployment state, not a code defect.
No services were started and no production provisioning was performed in this pass.


## Login-time enforcement, 2026-10-02

Normal login validates the signed local license, protected state and ordered licensed
seat allowance. Normal authenticated requests do not verify licenses or seats.
Suspension, expiry and seat changes affect the next login; hourly central Sync/Verify
continues unchanged. Logout bypasses the licensing guard. Administrator retains
recovery access. No device or session-count restrictions are enforced.

An invalid-license Super Admin login is admitted only for repair. The native session
stores that login's repair admission, and the request hook limits it to the existing
repair allowlist without rechecking signed licensing. After repair, logout and log in
again for normal ERP access and seat validation. A normal Super Admin login remains
unrestricted by licensing until its next login, even if the license later changes.

Validation: 31 isolated licensing tests and five initialized-site tests passed on
`retail-test.localhost`; site fixtures use temporary protected state and rollback,
with central HTTP responses mocked. Cached hooks were cleared. No browser check or
managed web-process restart was performed.

Logout follow-up: Frappe calls `on_login` again when switching to Guest during logout.
The login hook now explicitly skips Guest, and the session-creation hook avoids
persisting a Guest repair admission. Validation: 32 isolated tests and five site
tests passed; the actual Frappe logout-to-Guest hook sequence also passed with
session deletion mocked to preserve existing sessions.

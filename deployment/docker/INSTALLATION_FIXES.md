# Installation defects and permanent coverage

Supported integration baseline: Frappe 15.108.0, ERPNext 15.108.3,
HRMS 15.60.3. All fixes belong to Retail; no core application files are changed.

| Incident | Repository fix | Verification |
| --- | --- | --- |
| Licensing image selected instead of Retail | Deployment manager checks the image marker, pins its ID and ignores foreign shell/Compose settings | Wrong-image and shell-environment regression tests |
| Database password differed from `.env` | One persistent password file; only DB and temporary provisioner mount it; existing projects are not reinitialized | Deployment configuration and existing-file tests |
| `frappe:frappe` group did not exist | License directory uses `pwd` numeric service UID/GID, not a guessed group name | Numeric-group test preserving existing state |
| Counter/custom fields absent during setup | Prepare custom DocType fixtures first; run field-dependent hooks in `after_sync` | Real empty-site install; dependency tests |
| POS sync works locally but a new site lacks posting fields | Install completed-payload and settlement fields in `after_sync` and `after_migrate`, sharing definitions with legacy patches | Schema gate immediately after installation, before migration, and after repeated migration |
| Completed sale rejected when shift reference differs only in case | Compare the resolved shift document identity, using the same database lookup as session resolution; preserve the original payload | Case-variant, different-shift, cashier, branch, counter and terminal regressions |
| Standard Print Format rejected by recovery command | Normal installation/import context; no standalone fixture-repair command or developer-mode workaround | Real empty-site install |
| Workspace title collided with DocType routes | Correct all three Manufacturing fixture titles; repair their legacy DB titles before future exports | Shipped-route scan and repeated migrations |
| Naming-series choices and default conflicted | Remove stale numbering fixtures; exclude installer-owned options/defaults from export; prepare consistent compact numbering before field validation | Export-filter tests and full schema validation |
| Editable print format reused a unique code | Clear copied document code before inserting the new template | Copy regression and real editable-format creation |
| Recovery snippets had invalid syntax, directory or whitespace | Replace snippets with tracked CLI tools, explicit directories, shell/Python/lint checks and integration CI | Native installer and checked scripts |
| Old styling returned after rebuilding or mounting site volumes | Keep esbuild's chosen hash; reject ambiguous fallback; clean copied build output; restore image snapshots after install/migrate and runtime startup; serialize manifest writes | Old-hash/RTL/persisted-volume tests; frontend HTTP checks |
| Correct asset files still produce old styling after restart | Invalidate shared Redis `assets_json` after restoring image mappings, including startup without an active site | Startup cache regressions; installation gate seeds stale mappings, restarts services and checks authenticated Desk asset URLs |
| Central URL/public keys missing at activation | Deployment preflight requires validated HTTPS origin and public keys; per-site trust/state configuration is written during creation | Trust-validation tests |

`validate_fresh_install.sh` uses its own randomly named Compose project,
database, Redis, site and log volumes. It publishes no ports. It creates
`retail-test.localhost`, runs two migrations, validates every DocType referenced
by Retail field fixtures, starts a frontend/backend, logs in as Administrator,
and verifies the actual hashed CSS/JS referenced by Desk. Successful runs delete
only the test project's resources. Failed runs retain that test project.

License credentials and activation, business/company setup, POS accounting,
backups/restores and production HTTPS are environment-specific checks; a passing
installation gate does not claim those operations have been performed.

For new production installations use `manage.py` as documented in README.md.
Its configuration must not be pointed at a legacy manual stack's existing
database or site volumes. For a native Bench install, get the compatible
ERPNext/HRMS apps, install Retail normally and build assets normally; no manual
Counter import, fixture synchronization or temporary code editing is required.

Local databases can already contain patch-created fields, and developer mode
reads asset manifests directly. Production caches the merged asset manifest in
Redis. These differences can hide missing installer schema and stale asset-cache
bugs on a development bench. Rebuild the Retail image from the committed source,
recreate all application services with that image, and migrate each target site;
a Git pull alone does not update image-baked code. Run the isolated installation
gate on that candidate image before promoting it. Browser theme and column
preferences remain browser/user settings, rather than installation defaults.

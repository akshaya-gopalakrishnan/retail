# Persistent Retail Docker build

## New production installation

Use the tracked Containerfile and deployment manager, rather than copying an old
stack's Compose files or entering long recovery snippets. Supported baseline:
Frappe 15.108.0, ERPNext 15.108.3, HRMS 15.60.3. Retail source and generated image
must belong to the same release. Company setup, license activation and licensed
user assignment are customer-specific steps after infrastructure provisioning.

Build and pass the fresh-install gate below first. Then run on the Docker host
from the bench source directory containing `apps/retail` and `apps/hrms`:

```bash
python3 apps/retail/deployment/docker/manage.py init \
  --directory /opt/retail-production/runtime \
  --project retail-production --image retail-erpnext:YOUR_RELEASE \
  --site CUSTOMER_DOMAIN --port 8084 \
  --license-origin https://YOUR_LICENSE_SERVER \
  --public-key TRUSTED_BASE64_PUBLIC_KEY

python3 apps/retail/deployment/docker/manage.py create-site \
  --directory /opt/retail-production/runtime

python3 apps/retail/deployment/docker/manage.py up \
  --directory /opt/retail-production/runtime

python3 apps/retail/deployment/docker/manage.py status \
  --directory /opt/retail-production/runtime
```

`create-site` prompts for the Administrator password twice. The database root
password is generated once in a private file and passed only to MariaDB and the
temporary provisioner. The image is checked for the Retail build marker and
pinned by image ID; foreign shell variables or `.env` files cannot override it.
Existing deployment files, project volumes or site directories are never
overwritten. All persistent volumes are project-scoped, including licensing
state and the durable Redis queue. Each site gets its own state directory owned
by the image's actual numeric service UID/GID with mode 0700. Only public keys,
the HTTPS origin and the state path are configured; no signing private key,
customer license credentials, or demo token is copied.

Additional customers can share this production image and services while keeping
separate databases, files and license-state directories:

```bash
python3 apps/retail/deployment/docker/manage.py create-site \
  --directory /opt/retail-production/runtime --site NEXT_CUSTOMER_DOMAIN
```

Add each customer's own HTTPS/domain route. Image releases affect every site in
that production project; do not use the production project for demo/staging.

Choose a new directory **and project name** for a new environment. The example
project cannot be used on a VPS that already has the manually created
`retail-production` stack from INAYA provisioning: continue using that stack
until its deployment configuration is deliberately migrated. The manager does
not silently adopt an existing database or regenerate its password.

Add the customer's nginx/HTTPS route to the localhost frontend port separately.
Before handover, verify login, company setup, license activation/seats, a
representative POS/accounting flow and off-server backup restoration. Do not
delete production volumes as an asset-refresh or upgrade operation.

## Asset performance

The Containerfile explicitly builds Retail and HRMS bundles with `--production`.
It installs HRMS JavaScript dependencies from its lockfile before building;
Python package installation alone does not provide dependencies such as
`html2canvas`. HRMS postinstall also prepares its frontend and roster dependencies.
This keeps release builds minified even when a build environment enables developer
mode. Core application sources are unchanged.

For a local bench, run from the bench directory:

```bash
bash apps/retail/deployment/build_production_assets.sh
```

The script builds installed apps in production mode, checks required Desk bundles,
and invalidates only the runtime asset-map cache. Hard refresh the browser after
completion. An active `bench watch` or later development build can replace these
bundles with development output; use this script again for performance checks.
Developer mode and live reload remain available for normal development.

Do not compare a local `bench serve` session directly with production hosting:
production must serve assets through its frontend proxy with compression and
appropriate public-asset caching. Measure document response time, workspace/API
response time, and rendered card/chart readiness separately. Changes to caching
must keep authenticated HTML, APIs, and private files private.

## Fresh-install release gate

Before promoting a customer image, run:

```bash
bash apps/retail/deployment/docker/validate_fresh_install.sh retail-erpnext:YOUR_NEW_RELEASE_TAG
```

This creates a randomly named Compose project with its own database, Redis,
sites and logs, without publishing ports or mounting production storage. It
installs Frappe/ERPNext/HRMS/Retail into an empty `retail-test.localhost`, migrates
twice, and validates all DocTypes referenced by Retail custom-field fixtures
from a new container. Successful runs delete only this disposable project's
containers and volumes. Failed runs retain the test project for diagnosis.
Its temporary Compose JSON contains disposable passwords; do not publish it.
It also logs in as Administrator and verifies Desk includes its actual hashed
Retail CSS/JS and that the frontend serves LTR and RTL CSS with the correct MIME
types and Retail theme content. This gate does not replace visual browser,
accounting/POS, licensing, backup/restore,
or production runtime checks. Native CI runs these installation regression
modules separately; the complete legacy app suite remains available through
the CI workflow's manual `full_suite` option. That legacy combined suite has
separate test-context lifecycle problems and is not claimed green by this gate.

Custom DocType fixtures are prepared before custom fields are imported. Setup
that depends on fixtures runs in `after_sync`. Compact naming-series options
and defaults belong to `retail.short_codes.install`, not exported Property
Setter fixtures; exports exclude those properties to prevent drift.

Build from the bench source directory that contains `apps/retail` and `apps/hrms`.
Use the Containerfile tracked in the Retail repository:

```bash
cd /opt/retail/source/frappe-bench
docker build \
  -f apps/retail/deployment/docker/Containerfile \
  --build-arg ERPNEXT_IMAGE=frappe/erpnext:v15.108.3 \
  -t retail-erpnext:YOUR_NEW_RELEASE_TAG \
  .
```

The build calls `retail.build_asset_manifest` after building app bundles. It
preserves core mappings, adds Retail/HRMS CSS and JS mappings, uses `rtl_` keys
for RTL CSS, and fails if required Retail Desk assets are missing. Generated
bundles are build output and do not need to be committed.

Docker mounts the persistent `sites` volume over the image's `sites` directory.
An image-only manifest repair therefore does not repair an existing volume.
The build now also stores immutable manifest snapshots in
`/home/frappe/frappe-bench/.retail-image-assets`, outside that mount. The build
also combines the base image's core mappings with the new app mappings in its
baked `assets` directory. The Retail-owned entrypoint replaces the base script
that deletes/relinks shared assets at every start. On every container start,
initial installation and migration, `retail.build_asset_manifest.install` merges those snapshots into the
mounted manifests, ensures the app's public files are available, validates Desk
CSS/JS, and clears Frappe's global asset cache. It uses the image's exact hashes,
preserves older files, and does nothing on benches without an image snapshot.
Both build and migration discard unprefixed keys from the RTL manifest. Frappe
merges that manifest last, so stale LTR CSS or JS entries in it could otherwise
override the valid normal manifest and hide the theme even after installation.

Deploy to the intended environment's own Compose project. A demo/staging release
does not update production. For the existing shared demo/staging project,
Back up both sites before migration. Run `bench --site SITE migrate` on each
site: `retail.patches.repair_recovered_pos_display` backfills invoice links from
accepted transactions and repairs literal series titles on consolidated Sales
Invoices. It does not rewrite canonical request/response JSON or accounting.
Recovery refreshes those display links automatically for future bills.

Verify the new image on backend, workers and scheduler; check both site
migrations, HTTP asset requests, list display, and a representative new POS bill.
The existing POS acceptance receipt remains immutable: Success means accepted;
current posting state is in POS Accepted Transaction.
Only Success/Duplicate sale receipts get recovered invoice links. The migration
`retail.patches.repair_failed_pos_log_links` clears links previously copied to
failed attempts sharing the same external reference. It preserves their status,
error, canonical payload, response and operation key.

If verifying a rollout, inspect the deployed manifest inside the backend:

```bash
bench --site demo.celestial.it.com execute retail.build_asset_manifest.install
```

Use this only in an image built with the tracked Containerfile. A return value
of `False` means the image has no snapshot: rebuild using the Containerfile
above. Check the mapped URLs return HTTP 200 from the frontend, and compare
the same browser route after a hard refresh. Never delete site volumes to
refresh assets.

# Persistent Retail Docker build

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
`/home/frappe/frappe-bench/.retail-image-assets`, outside that mount. On every
migration, `retail.build_asset_manifest.install` merges those snapshots into the
mounted manifests, ensures the app's public files are available, validates Desk
CSS/JS, and clears Frappe's global asset cache. It uses the image's exact hashes,
preserves older files, and does nothing on benches without an image snapshot.

Deploy the new tag through the existing shared demo/staging Compose project.
Back up both sites before migration. Run `bench --site SITE migrate` on each
site: `retail.patches.repair_recovered_pos_display` backfills invoice links from
accepted transactions and repairs literal series titles on consolidated Sales
Invoices. It does not rewrite canonical request/response JSON or accounting.
Recovery refreshes those display links automatically for future bills.

Verify the new image on backend, workers and scheduler; check both site
migrations, HTTP asset requests, list display, and a representative new POS bill.
The existing POS acceptance receipt remains immutable: Success means accepted;
current posting state is in POS Accepted Transaction.

If verifying a rollout, inspect the deployed manifest inside the backend:

```bash
bench --site demo.celestial.it.com execute retail.build_asset_manifest.install
```

Use this only in an image built with the tracked Containerfile. A return value
of `False` means the image has no snapshot: rebuild using the Containerfile
above. Check the mapped URLs return HTTP 200 from the frontend, and compare
the same browser route after a hard refresh. Never delete site volumes to
refresh assets.

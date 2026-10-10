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

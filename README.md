### Retail

Retail application, including POS and Van Sales.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench --site $SITE_NAME install-app retail
bench --site $SITE_NAME migrate
bench build --app retail
bench --site $SITE_NAME clear-cache
```

### Source location and POS settings

The canonical source is `apps/retail`. The Python package and `/assets/retail`
symlink must both resolve to this directory. Do not register another checkout
containing the same `retail` Python package alongside this one.

Employee **POS Settings** contains POS login fields and the assigned
**POS Operator Privilege** profile. System Managers define profiles and assign
them to Employees. All 37 flags are sent in operator master sync; unassigned or
disabled profiles deny all actions. See [POS_API_CONTRACT.md](POS_API_CONTRACT.md)
for the .NET contract and client enforcement requirements.

The tab is installed by the retail migration/install hooks; no ERPNext or HRMS
core changes are required. Existing assignments and PIN hashes are preserved.

### API documentation

[POS_API_CONTRACT.md](POS_API_CONTRACT.md) is the consolidated integration reference
for master data, shifts, sales, returns, payments, promotions, loyalty, gift
vouchers, day closing and manager corrections. Each API has request and response
examples for the .NET team.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/retail
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### Document list defaults

Retail ships the saved column order and column counts in
`retail/fixtures/list_view_settings.json`. Supporting field visibility and titles
are included in the Property Setter and Custom Field fixtures; shared list
behavior lives in Retail's list JavaScript. Frappe imports these fixtures on
installation and migration, so these layouts travel with the app.

After intentionally changing the defaults on the source site, export fixtures
with `bench --site <source-site> export-fixtures --app retail` and review the
fixture changes before shipping them. UI changes are not automatically written
back to the app. Migration can overwrite site-specific saved list layouts with
the shipped fixtures.

### Optional shared asset CDN (Cloudflare R2)

CDN routing is disabled by default. It changes only published bundle URLs;
login, authenticated API responses, private files, and business data remain on
the ERP host. A CDN does not replace backend/API performance work.

Create a Cloudflare account, an R2 bucket dedicated to public app assets, and a
custom bucket domain such as `assets.celestial.it.com`. The hostname must be
active before enabling routing. The `r2.dev` URL is a development endpoint,
not the production caching domain. Apply `deployment/r2-cors.json` as the
bucket CORS policy: GET/HEAD from any installation, without credentials.
See [R2 custom domains](https://developers.cloudflare.com/r2/buckets/public-buckets/)
and [CORS configuration](https://developers.cloudflare.com/r2/buckets/cors/).

Build production assets for every installed app before packaging. From the bench:

```sh
bench build --production
python3 apps/retail/deployment/build_cdn_release.py --output /tmp/retail-cdn-release --origin https://assets.celestial.it.com
```

The packager emits a release directory, CDN base URL, and manifest path. It
includes public JS/CSS, images, fonts, and audio; excludes source maps and
private/site files; rewrites absolute CSS asset references to the release URL.
All bundled files must exist. Keep every published release immutable and retain
older releases while installations still use them.

Install AWS CLI and configure bucket-scoped R2 credentials through an AWS
profile/environment, outside the repository. Never put credentials in site
config, command arguments, or chat. Inspect the upload plan first:

```sh
python3 apps/retail/deployment/publish_cdn_release.py --directory /tmp/retail-cdn-release/RELEASE --bucket BUCKET --account-id ACCOUNT_ID
```

Replace those placeholders with the packager output and Cloudflare values.
Add `--upload` to execute the plan. The publisher checks asset hashes, uploads
assets first and the manifest last, and never deletes old releases. Use cache
rules for the dedicated asset hostname and verify compression, correct MIME
types, CORS headers, and `CF-Cache-Status: HIT` on repeated asset requests.

Copy the manifest to a persistent deployment-owned location on each matching
ERP host. Set `retail_cdn_url` to the emitted release base URL and
`retail_cdn_manifest` to that local manifest's absolute path in site config.
Clear the site's cache after enabling or disabling routing. Omit/remove both
settings to disable it. A missing/incomplete manifest, non-HTTPS URL, or build
mismatch automatically keeps local URLs. Repackage and activate the new
manifest after every asset build/upgrade.

Initial script errors trigger a parser-ordered local retry; stylesheet errors
retry locally. Desk lazy bundle requests retry locally after CDN errors or a
five-second timeout. Requests for public CDN content omit credentials. If both
lazy sources fail, the promise rejects and releases the frozen UI. Existing
inline-script permissions are needed for initial retry, as for Frappe's boot.

Before activation, verify login and authenticated Desk, form/list/report pages,
label printing, lazy CSS, fonts, Arabic/RTL, and local fallback with CDN requests
blocked. Test both fresh and warm browser caches. No account, bucket, DNS,
upload, or production activation is performed by installing this app.

### License

mit

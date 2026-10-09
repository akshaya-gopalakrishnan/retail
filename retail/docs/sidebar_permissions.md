# Retail Sidebar Permissions

User → Roles & Permissions now includes **Retail Sidebar Permissions** directly
after Allow Modules. It uses Frappe's native MultiCheck control and ordinary User
Save. The editor fills the form width and uses five desktop columns, three below
1200px, two below 768px and one below 480px.

Only Administrator and the existing protected **Super Admin** identity can change
the selection. That identity is the assigned role, not the editable Role Profile
label. Existing `retail.access_control` protections prevent customer administrators
from assigning or changing this exemption. Assigned Super Admin users retain native full access.
Authorized administrators can edit and save selections on exempt User records;
the editor displays the saved selection. The built-in Administrator now follows
its saved selections for sidebar visibility and direct URL/API restrictions.
With no saved configuration it retains legacy access. Its own User form, document
load and save remain reachable for permission recovery, subject to native checks;
this exception does not grant access to the User list or other users.

## Persistence and migration

The Retail install/migrate hook creates three User Custom Fields: a section, HTML
editor and hidden `retail_sidebar_permissions` Long Text field at permission level 1.
No core source or DocPerm is changed and no roles are automatically assigned.

An empty field preserves the user's existing native/Retail permissions. Changing
and saving any checkbox creates versioned JSON with an explicit allowed identifier
list. An empty list restricts every checklist menu; unlisted access retains native permissions. A parent is persisted only when at least
one child is selected; changing a parent selects or clears its children. New registry
identifiers are absent from existing selections and default to denied.

Administrative API writes may clear the field to restore legacy unrestricted menu
selection. This still retains all existing native role, module, Van Sales, POS and
Celesta access checks.

Deploy with:

```sh
bench --site retail-test.localhost migrate
bench build --app retail
bench --site retail-test.localhost clear-cache
```

Use the normal production process reload when deploying Python changes. Existing
sessions receive a user-specific refresh event after a changed selection commits;
server authorization reads the saved selection on each new request. No existing
user is opted into restrictions by migration. The same idempotent Custom Field
setup runs after installation on fresh sites; a separate fresh-site installation
has not been provisioned during this validation.

## Registry

`sidebar_routes.json` and `sidebar_labels.json` are the extracted existing browser
route and label registries. Both are served in boot and consumed by the browser
and Python. `sidebar_registry.py` reuses those mappings, the existing server sidebar
groups/report definitions, and Retail Workspace files for editor entries, stable
workspace identifiers, display labels and order. The canonical Business Home
fixture takes precedence over the legacy duplicate `home/home.json`.

Add a new menu to the shared registry; do not create an independent editor list.
Preserve established IDs when renaming labels. Restricted users must explicitly
receive the new ID. Entries outside the checklist retain existing native access. Only known unchecked
entries and their mapped targets are restricted.

## Enforcement and necessary boundaries

Selections can only **remove** access. Native DocPerms, role permissions, field
permissions, User Permissions and existing Retail restrictions continue to decide
Read, Create, Write, Submit, Cancel, Delete, Print, Export and other actions.

The authenticated request boundary checks direct Desk URLs, native document/list
RPCs, REST v1/v2 document routes, explicit controller helpers, reports and page
loaders. Shared-DocType queries receive extra native permission-query conditions
only for the externally requested list. Root documents and their previous persisted
classification are checked before modification and again after validation. Bulk
deletion validates every requested record before Frappe can enqueue deletion.

The additional permission hooks are registered only on mapped DocTypes and are
inactive for unrelated documents, linked records and jobs. Internal GL/SLE creation,
stock/accounting lookups and integration work retain their existing behavior. Native
link selection and metadata remain available under their existing permissions;
allowing an invoice must not make its linked Customer/Item lookup fail. This does
not give access to the denied Customer list, form or mutation API.

Shared records follow these rules:

- Sales Invoices and Sales Returns distinguish `Sales Invoice.is_return`.
- Purchase Receipts and Purchase Returns distinguish `Purchase Receipt.is_return`,
  matching the existing Purchase Returns route. Purchase Invoice records remain
  under Purchase Invoices; there is no separate purchase-invoice-return menu.
- Manufacturing Stock Entries cover Manufacture, Material Transfer for Manufacture
  and Material Consumption for Manufacture. Other standard purposes belong to Stock
  Adjustments. Van stock entries use their existing Van flag and menu.
- Customer, Payment Entry, Material Request and Sales Invoice separate ordinary
  records from their existing Van flags. A Van page does not unlock the ordinary menu.
- Item and Warehouse are deliberately shared by their standard and Van menus.

Reports and pages use their own route capabilities followed by native access checks.
If the same report/page is exposed by multiple selected menus, any one selected
menu authorizes that shared target. Native report data may include linked records
outside the selected document menus; report capability and native report permission
govern that report. A checkbox cannot redefine the report's own data model.

Public services that bypass ordinary document permissions need explicit entries in
`sidebar_services.py`. The POS services retain existing endpoints/payloads, with
additional selected-capability and native action requirements for restricted users.
Unclassified RPCs, unlisted DocTypes, pages, reports, dashboard configuration and
native helpers retain their own existing permission checks. The checklist is an
additional restriction on unchecked entries, not an allowlist of all ERP access.
Mapped Retail services still enforce their corresponding checklist capability.

## Changed sources and validation

New sources: `sidebar_registry.py`, `sidebar_permissions.py`, `sidebar_services.py`,
`sidebar_routes.json`, `sidebar_labels.json`, `public/js/forms/sidebar_permissions.js`,
`public/css/sidebar_permissions.css`, and `test_sidebar_permissions.py`.

Existing sources changed: `hooks.py`, `workspace_permissions.py`,
`public/js/retail_navigation.js`, `public/retail_desk.bundle.scss`. The existing Driver
navigation test now reads the shared registries; the report-sidebar unit suite
explicitly models a legacy unrestricted user.

Validation scripts and results are under `apps/retail/validation/`:

- `sidebar_permissions_live.py` exercises temporary users, native/API restrictions,
  save/reload, login, isolation, reports/pages, exemptions and native role intersection.
  Temporary login admission hooks are mocked only inside this test process; production
  licensing is unchanged. It runs 43 new/existing Python permission/navigation tests.
  Use `--permissions-only` to repeat the permission checks while retaining the
  separately completed POS regression evidence; results identify this explicitly.
- `sidebar_permissions_browser.py` / `.cjs` use a temporary local Frappe server,
  disposable user, isolated Chromium profile and temporary sessions. Results and
  desktop/mobile screenshots are saved beside the scripts.
- The existing three Node navigation suites run independently.
- POS posting/idempotency and accounting/stock regressions run with rollback fixtures.
  The full legacy realtime suite attempts cancellation of a completed immutable bill
  and conflicts with the existing cancellation guard. The legacy exchange suite
  expects immediate failure for over-return, whereas the current durable-acceptance
  policy can accept it with a settlement reconciliation exception. These existing
  policy/test conflicts are recorded rather than changing POS behavior.

The browser harness uses the cached Chromium executable and a locally extracted
`libasound2` under `/tmp/retail-sidebar-browser-libs`; it does not install system packages.

Transaction forms retain narrowly mapped native link facts and calculation helpers,
including VAT and rounding, subject to native permissions. This does not authorize
full linked documents or their lists. Family List does not authorize the Items list.
Private attachments require access to their attached document. Native background
list exports retain the same return, Van and manufacturing query restrictions.

Personal Dashboard Settings lookups are limited to the signed-in user's name;
creation and chart preference updates remain personal UI operations. Business Home
authorizes its stock-count helpers under native Item/Bin read permissions, and
chart definitions/source configuration only from the persisted Home widget list.
These dependencies do not authorize arbitrary widget definitions or business records.
Item forms and transaction forms also retain narrowly mapped margin/VAT lookups,
stock-dashboard reads, Arabic name translation, payment-reference indicators and
two stock-preference fields. These preserve selected-menu and native permission
requirements; settings writes and arbitrary settings reads remain restricted.

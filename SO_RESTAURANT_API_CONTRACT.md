# Sales Order and Restaurant API Contract for .NET

Implement Sales Order entry and restaurant table synchronization using the existing Retail ERP APIs. Examples use sample IDs; replace them with downloaded ERP values. Development site: `retail-test.localhost`.

Restaurant support here covers table masters and their location names. There are no dedicated restaurant APIs for table occupancy, reservations, kitchen tickets, table transfers, split bills or restaurant order posting. A Sales Order does not assign or reserve a restaurant table. POS invoicing, payments, shifts, closing and promotions use the separate POS contract.

## Connection and endpoint index

```text
Base URL: https://<erp-address>
Content-Type: application/json
Accept: application/json
Authorization: token <api_key>:<api_secret>
```

Use your actual ERP deployment URL. Session authentication is also supported: retain the `sid` cookie and send the CSRF header as explained below. Use individual ERP users for Sales Orders.

| Purpose | Method | Path |
| --- | --- | --- |
| ERP login | POST | `/api/method/login` |
| Logout | POST | `/api/method/logout` |
| Get session CSRF token and SO permissions | GET | `/api/method/retail.api.pos_sync.get_sales_order_data` |
| SO masters, order lists and document reads | POST | `/api/method/retail.api.pos_sync.get_sales_order_data` |
| Customer with addresses and contacts | POST | `/api/method/retail.api.pos_sync.upsert_customer` with `context: "sales_order"` |
| Calculate, save or submit SO | POST | `/api/method/retail.api.pos_sync.save_sales_order` |
| Restaurant counter connection check | GET | `/api/method/retail.api.pos_sync.health_check` |
| Restaurant tables and location names | GET | `/api/method/retail.api.pos_sync.get_pos_tables` |

Sales Orders use normal ERP document permissions. Restaurant downloads require POS module access and `POS Integration User` (or `System Manager`), plus counter authorization. SO permissions alone do not grant restaurant download access.

Replies normally wrap endpoint results in `message`; login and logout have the shapes shown below. Use decimal arithmetic for monetary values in .NET. Preserve ERP identifiers and exact modification timestamps.

## Sales Order APIs


These additions use the same ERP and API file. Existing POS requests stay the same.
Sales Order entry uses two endpoints and the Sales Order mode of **upsert_customer**.
No cashier, PIN, shift, counter, or POS Integration User role is required for this mode.
Use the logged-in ERP user's existing document permissions. Save requires Create/Write;
submit also requires Submit. ERP's normal validations and configured workflows still apply.
Users are created in ERP; the app does not register users.

### Login and logout (existing ERP APIs)

`POST /api/method/login`

```json
{"usr":"salesperson@example.com","pwd":"<ERP password>"}
```

Successful response example:

```json
{"message":"Logged In","home_page":"/app","full_name":"Sales Person","sales_person_id":"SP2-2","sales_person_name":"Mith"}
```

`sales_person_id` and `sales_person_name` are added to the existing response using
the authenticated User → active Employee → enabled, non-group Sales Person link.
Both are `null` if a link is missing or more than one matching Employee or Sales
Person exists. Existing login fields, cookies and authentication rules remain
unchanged. These identity fields do not grant access or filter customer records.

Keep the returned `sid` cookie and send it on every following request. ERP authentication
settings, including two-factor authentication where enabled, still apply. Session-authenticated
POST requests must follow the ERP's CSRF requirements. Immediately after login, call
`GET /api/method/retail.api.pos_sync.get_sales_order_data` and read `message.csrf_token`.
Send that value in `X-Frappe-CSRF-Token` on subsequent session-authenticated POST requests. An existing per-user API token is also supported
using the Authorization header documented above. Do not use shared POS credentials for
individual salesperson orders.

`POST /api/method/logout` ends the session. It normally returns an empty JSON object.

All following examples use `Content-Type: application/json`. Replies are inside `message`.
Sample IDs below must be replaced with IDs downloaded from your ERP.

### 1. Download masters, list orders, or read one record

`POST /api/method/retail.api.pos_sync.get_sales_order_data`

Combine as many needed master queries as practical in one call. Default page size is 1,000;
maximum is 5,000 per query. When `has_more` is true, send `next_start` as `start` for that
query. Lists are ordered by modified time and name. For an incremental refresh, use a
modified-time filter with a small overlap and merge records by name. Refresh periodically
for deleted records; this API does not return deletion markers.

```json
{
  "queries": [
    {"doctype":"Company","fields":["name","default_currency"]},
    {"doctype":"Customer","include_details":true,"page_length":1000},
    {"doctype":"Address","include_details":true,"page_length":1000},
    {"doctype":"Contact","include_details":true,"page_length":1000},
    {"doctype":"Item","filters":{"is_sales_item":1,"disabled":0},"include_details":true,"page_length":1000},
    {"doctype":"Item Price","include_details":true,"page_length":5000},
    {"doctype":"Warehouse","fields":["name","company","is_group","disabled"]},
    {"doctype":"Price List","fields":["name","currency","selling","enabled"]},
    {"doctype":"Customer Group","fields":["name","is_group"]},
    {"doctype":"Territory","fields":["name","is_group"]},
    {"doctype":"Country","fields":["name"]},
    {"doctype":"Payment Terms Template","include_details":true}
  ]
}
```

`include_details: true` returns full permitted documents including child rows. For Items
this includes configured UOM conversions, barcodes and Retail packing details. For Address
and Contact it includes their Customer links. It does not add the computed POS stock,
batch, serial or promotion snapshots: existing POS clients can keep using the existing
master/stock/promotion APIs unchanged. Sales Order users do not need those snapshots to
save an order; ordering does not itself issue stock.

Without `include_details`, request just the fields the app needs. If fields are omitted,
only `name` and `modified` are returned. Only request DocTypes the user can read; a denied
query fails the request rather than silently returning incomplete masters.

Response example (shortened):

```json
{
  "message": {
    "status":"Success",
    "server_time":"2026-10-29 12:00:00",
    "csrf_token":"<session CSRF token>",
    "user":"salesperson@example.com",
    "permissions":{"read":true,"create":true,"write":true,"submit":true},
    "results":[
      {"doctype":"Company","documents":[{"name":"Example Company","default_currency":"AED"}],"has_more":false,"next_start":1},
      {"doctype":"Customer","documents":[{"name":"C-100","customer_name":"Sample Customer","customer_type":"Company","customer_group":"Commercial","territory":"Dubai","modified":"2026-10-29 11:00:00"}],"has_more":false,"next_start":1}
    ]
  }
}
```

Results follow the same order as the queries; the example shows only the first two.
Other supported masters: Currency, UOM, Terms and Conditions, Sales Taxes and Charges
Template, Item Tax Template, Cost Center, Project, Sales Person, Sales Partner, Tax Category,
Shipping Rule, Incoterm, Brand and Item Group.

List orders using this same API:

Sales Orders include `sales_person_id` and `sales_person_name`. New orders receive
these from the creating user's linked active Employee / enabled Sales Person.
Unmapped or ambiguous creators receive null values. The ID can be changed while
the order is a draft; the name follows that ID. Both are locked after submission.
Existing orders are not backfilled. Full-document reads and save responses include
these fields. Order lists automatically include both fields, even when omitted
from the requested `fields`. Orders without an assigned salesperson return null
values. This does not add backend access restrictions.

```json
{"queries":[{"doctype":"Sales Order","fields":["name","customer","customer_name","sales_person_id","sales_person_name","transaction_date","delivery_date","grand_total","currency","status","docstatus","modified"],"page_length":1000}]}
```

To download orders for the salesperson returned at login, use that login's
`sales_person_id` in `filters` (replace the example `SP2-2`):

```json
{"queries":[{"doctype":"Sales Order","fields":["name","customer","sales_person_id","sales_person_name","grand_total","status","modified"],"filters":{"sales_person_id":"SP2-2"},"page_length":1000}]}
```

Both identity fields appear on each order inside
`message.results[0].documents`. Shortened response example:

```json
{"message":{"status":"Success","results":[{"doctype":"Sales Order","documents":[{"name":"SO-100","customer":"C-100","sales_person_id":"SP2-2","sales_person_name":"Mith","grand_total":210,"status":"Draft","modified":"2026-11-04 12:00:00.000000"}],"has_more":false,"next_start":1}]}}
```

The save/submit response includes the same fields at
`message.order.sales_person_id` and `message.order.sales_person_name`.

Use `filters` for customer, dates, status, owner, etc. No extra own-order restriction is added.
Read an order or master with its full permitted child rows:

```json
{"queries":[{"doctype":"Sales Order","name":"RTL-SO-2026-00001"}]}
```

```json
{"message":{"status":"Success","server_time":"2026-10-29 12:00:00","user":"salesperson@example.com","permissions":{"read":true,"create":true,"write":true,"submit":true},"results":[{"doctype":"Sales Order","documents":[{"name":"RTL-SO-2026-00001","docstatus":0,"customer":"C-100","items":[{"item_code":"ITEM-001","qty":2,"uom":"Nos","rate":100}],"grand_total":210,"modified":"2026-10-29 12:00:00.123456"}],"has_more":false}]}}
```

Full documents contain more fields than these shortened examples.

### 2. Create/update customer, addresses and contacts together

Reuse `POST /api/method/retail.api.pos_sync.upsert_customer`.

Only the explicit `context: "sales_order"` selects this new shape. Existing POS customer
requests without this context keep their original behaviour.

```json
{
  "context":"sales_order",
  "external_customer_id":"APP-CUSTOMER-8f9c2a",
  "customer":{
    "customer_name":"Sample Customer",
    "customer_type":"Company",
    "customer_group":"Commercial",
    "territory":"Dubai",
    "tax_id":"100000000000003",
    "default_currency":"AED",
    "default_price_list":"Standard Selling"
  },
  "addresses":[
    {"address_type":"Billing","address_line1":"Shop 10","city":"Dubai","country":"United Arab Emirates","emirate":"Dubai","is_primary_address":1},
    {"address_type":"Shipping","address_line1":"Warehouse 2","city":"Dubai","country":"United Arab Emirates","is_shipping_address":1}
  ],
  "contacts":[
    {"first_name":"Ahmed","is_primary_contact":1,"phone_nos":[{"phone":"971500000001","is_primary_mobile_no":1}],"email_ids":[{"email_id":"ahmed@example.com","is_primary":1}]}
  ]
}
```

```json
{"message":{"status":"Success","action":"Created","customer":"C-100","addresses":["Sample Customer-Billing","Sample Customer-Shipping"],"contacts":["Ahmed-C-100"]}}
```

For updates, send `customer.name`, and the existing `name` inside each Address/Contact row
being updated. Omitted fields stay unchanged; supplied child arrays replace those arrays.
New address/contact rows without a name create records. The API links them to the Customer.
Addresses require type, line 1, city and country. Send phone/email through Contact child rows.
The whole request succeeds or fails together through ERP's normal request transaction.

```json
{"context":"sales_order","customer":{"name":"C-100","tax_id":"100000000000003"},"addresses":[{"name":"Sample Customer-Billing","address_line1":"Shop 11"}],"contacts":[{"name":"Ahmed-C-100","phone_nos":[{"phone":"971500000002","is_primary_mobile_no":1}]}]}
```

```json
{"message":{"status":"Success","action":"Updated","customer":"C-100","addresses":["Sample Customer-Billing"],"contacts":["Ahmed-C-100"]}}
```

Keep a stable external_customer_id for new customers. After a timeout, retrieve the customer
by external_pos_customer_id and read its linked addresses/contacts before resending new nested
rows; unnamed nested rows are not retry receipts. This avoids duplicate addresses/contacts.

### 3. Calculate, save or submit a Sales Order

`POST /api/method/retail.api.pos_sync.save_sales_order`

The same API handles all three actions:

- `calculate`: validate and calculate; no order is saved.
- `save`: save a draft.
- `submit`: save and submit immediately, or submit an existing draft.

New order example — change only `action` to calculate/save/submit:

```json
{
  "action":"submit",
  "client_order_id":"ORDER-550e8400-e29b-41d4-a716-446655440000",
  "order":{
    "company":"Example Company",
    "customer":"C-100",
    "transaction_date":"2026-10-29",
    "delivery_date":"2026-10-30",
    "currency":"AED",
    "selling_price_list":"Standard Selling",
    "set_warehouse":"Stores - EC",
    "customer_address":"Sample Customer-Billing",
    "shipping_address_name":"Sample Customer-Shipping",
    "contact_person":"Ahmed-C-100",
    "po_no":"CUSTOMER-PO-100",
    "items":[
      {"item_code":"ITEM-001","qty":2,"uom":"Nos","rate":100,"custom_foc_qty":0}
    ]
  }
}
```

```json
{
  "message":{
    "status":"Success",
    "action":"submit",
    "duplicate":false,
    "name":"RTL-SO-2026-00001",
    "docstatus":1,
    "order":{
      "name":"RTL-SO-2026-00001",
      "docstatus":1,
      "customer":"C-100",
      "currency":"AED",
      "items":[{"item_code":"ITEM-001","qty":2,"uom":"Nos","conversion_factor":1,"rate":100,"amount":200,"custom_rate_including_vat":105,"custom_vat_amount":10}],
      "net_total":200,
      "total_taxes_and_charges":10,
      "grand_total":210,
      "modified":"2026-10-29 12:00:00.123456"
    }
  }
}
```

Amounts above assume an item with 5% VAT. Actual tax follows ERP configuration. Responses
return the full permitted order, including calculated child rows and totals.
`save` returns docstatus 0; `submit` returns docstatus 1. `calculate` returns name null,
docstatus 0 and a preview document; its temporary document name is not an ERP order ID.

Send a globally unique client_order_id (maximum 140 characters) for every new order.
On timeout, retry the same action/body/ID. An existing reference returns the existing order
with duplicate true; changed order data in that retry is ignored. A submit retry can submit
the previously saved draft. Parallel first sends may return a unique-reference conflict;
retry the same ID after the first request finishes. Never generate a new ID to retry.

Update an existing draft using its name and exact latest modified value:

```json
{"action":"save","name":"RTL-SO-2026-00001","modified":"2026-10-29 12:00:00.123456","order":{"po_no":"UPDATED-PO","items":[{"item_code":"ITEM-001","qty":3,"uom":"Nos","rate":100}]}}
```

Response uses the same shape with action save, docstatus 0 and updated totals/modified.
When items is supplied it replaces the draft's complete item list. Omit it to keep the items.
If ERP changed the draft, download it again before updating.

Submit an existing draft without changing its fields:

```json
{"action":"submit","name":"RTL-SO-2026-00001","modified":"2026-10-29 12:01:00.123456"}
```

Response uses the same shape with action submit and docstatus 1. Submitted documents cannot
be edited through this API. Use the existing ERP cancellation/amendment workflow if needed.

Pricing and field rules:

- `rate` excludes VAT. For POS-style inclusive input, send only `custom_rate_including_vat`
  instead of rate. Do not send conflicting exclusive/inclusive rates. ERP calculates VAT.
- Use ERP item/UOM/warehouse IDs. ERP fetches item defaults, conversion factors and pricing.
- `qty` is paid quantity; `custom_foc_qty` is additional free quantity.
- Optional normal fields include payment_terms_template, tc_name, terms, po_date, cost_center,
  project, sales_team, per-row warehouse/delivery_date, discount_percentage/discount_amount,
  additional_discount_percentage, apply_discount_on, and the configured UAE detail fields.
- ERP chooses the order number and records the actual logged-in creator. System fields,
  flags and read-only calculated fields from client JSON are ignored. Existing ERP hooks
  calculate VAT/FOC and perform their normal submit actions.
- The app does not create invoices, delivery notes or collect payments through this API.
- Standard ERP errors use a non-success HTTP status and fields such as exc_type and
  _server_messages. Show the ERP validation message. A permission error means the ERP role
  needs the relevant permission; no extra app-specific server role is required.

Deployment: run the normal Retail site migration before using these APIs. It adds only the
unique App Order ID field needed for safe order retries. Development field setup and
rollback-only integration verification were performed on retail-test.localhost.

## Restaurant APIs

### Setup and authorization

Configure a Branch and an active POS Branch Counter with offline sync enabled. Send `branch` and `counter_code` on both GET requests. If a counter has an assigned integration user, it must match the authenticated user; System Managers retain support access. Neither endpoint opens a cashier shift.

Maintain tables and locations in ERP. Locations are returned as names inside table rows; there is no separate location download endpoint. Locations without tables are not returned as standalone records.

### Check the configured counter


`GET /api/method/retail.api.pos_sync.health_check?branch=Karama&counter_code=C001`

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "status": "OK",
    "company": "nesto",
    "branch": "Karama",
    "warehouse": "Stores - N",
    "cost_center": "Main - N",
    "counter": "Karama-C001",
    "terminal_id": "T001",
    "printer_name": "Receipt Printer 1",
    "server_time": "2026-06-25 12:00:00"
  }
}
```

### Download tables and locations


`GET /api/method/retail.api.pos_sync.get_pos_tables?branch=Karama&counter_code=C001`

Use the same token credentials, POS authorization and assigned-counter checks as the other POS APIs. Request body: none.
This endpoint is read-only and independent of `get_pos_master_data`; existing master payloads are unchanged.

Response example (sample table and location):

```json
{
  "message": {
    "status": "Success",
    "server_time": "2026-11-17 14:30:00.000000",
    "tables": [
      {
        "table_id": "1",
        "table_name": "T01",
        "branch": "Karama",
        "table_location": "Ground Floor",
        "seating_capacity": 4,
        "is_active": true,
        "is_deleted": false,
        "created_by": "Administrator",
        "created_on": "2026-11-17 14:00:00.000000",
        "modified_by": "Administrator",
        "modified_on": "2026-11-17 14:20:00.000000"
      }
    ]
  }
}
```

| JSON field | .NET / SQL meaning |
| --- | --- |
| `table_id` | Automatically generated ERP table ID. Keep this stable key for upserts; do not match by table name. Returned as a numeric string. |
| `table_name` | Table Number / Name entered in ERP. |
| `branch` | The Branch selected on the table, independent of the requesting counter. Required on new/edited tables; `null` on legacy tables awaiting assignment. |
| `table_location` | Location name, such as Ground Floor; not the location ID. |
| `seating_capacity` | Integer seating capacity. |
| `is_active` | `IS_ACTIVE` (`bit`), from the table's Enabled checkbox. Disabled tables are included. |
| `is_deleted` | `IS_DELETED` (`bit`). Returned ERP rows are existing records, so this is `false`; handle removed rows using the snapshot rule below. |
| `created_by` | `CREATED_BY`, ERP creator's User ID (same identity convention as item masters). |
| `created_on` | `CREATED_ON`, ERP creation timestamp. |
| `modified_by` | `MODIFIED_BY`, ERP last editor's User ID. |
| `modified_on` | `MODIFIED_ON`, ERP last modification timestamp. |

**Snapshot and deletion rule:** Every successful response contains all tables on this ERP site, including disabled tables. Each row includes its own `branch`. The request branch identifies and authorizes the POS counter; it does not filter table rows. Different authorized counters receive the same complete site-wide table master. The .NET app can filter by each row's `branch` after saving the complete snapshot. The Tables form defaults Branch when the site has exactly one; otherwise the user must choose it. No `modified_after` cursor is used. Download this endpoint alongside normal master synchronization. Location renames are reflected on the next download even when the table itself was not edited.

Save the entire reply in one local transaction: upsert by `table_id`, then set `IS_DELETED = 1` and `IS_ACTIVE = 0` for previously downloaded ERP table IDs absent from this snapshot. Scope that reconciliation to the same ERP site/connection, not local-only tables or another ERP site. An empty `tables: []` in a successful reply means there are no tables. On authentication, transport, parsing or database-save failure, retain the previous snapshot and do not mark anything deleted. Returned IDs always have `is_deleted: false`, which also clears a prior local deletion marker if a record reappears. Removed rows have no ERP modification timestamp in this endpoint; do not invent one.

Audit timestamps use the ERP site's configured timezone, as with the other POS APIs. Preserve the original values in the DTO; conversion to SQL `smalldatetime` loses seconds and subsecond precision. ERP User IDs may exceed `nvarchar(50)`; use a sufficiently wide audit column (up to 140 characters) instead of silently truncating identities.

## Integration sequence

1. Configure the ERP URL and credentials. Log in and obtain the CSRF token when using sessions.
2. Download the permitted SO masters, including ERP Customer, Item, UOM, Warehouse and price list IDs. Follow pagination for every query.
3. Create or update customers, addresses and contacts if the app supports customer maintenance.
4. Call `calculate` for ERP validation and totals when a preview is needed.
5. Persist a unique `client_order_id` with the intended save/submit request locally. Send `save` for a draft or `submit` for posting.
6. Store the returned ERP name, exact `modified`, totals and `docstatus`. Show submitted only when `docstatus` is 1.
7. Retry timeouts with the same `client_order_id`. For draft edits, use the latest downloaded `modified`.
8. Using authorized POS credentials, check the restaurant counter and download the full table snapshot. Save atomically, then filter displayed tables by each row's branch and active status.

## Error handling and acceptance checks

Check HTTP status and the JSON result. ERP authentication, permission and validation errors may return non-success HTTP codes with `exc_type` and `_server_messages`. Display the ERP message. A transport timeout does not establish that saving failed; retry the same SO ID.

| Check | Expected result |
| --- | --- |
| Calculate valid SO | Preview totals; no saved order name |
| Save new SO | ERP name and `docstatus: 0` |
| Submit SO | ERP name and `docstatus: 1` |
| Retry same SO ID | Same order, `duplicate: true`; no second order |
| Edit with stale `modified` | `TimestampMismatchError`; download and reconcile current order |
| Submit without permission | ERP permission error |
| Download tables | Complete site snapshot, including disabled tables and each row's branch |
| Successful empty table snapshot | Cached ERP tables marked deleted within the same connection |
| Failed download or local database save | Previous table snapshot retained; no deletion reconciliation |

Use `retail-test.localhost` for integration tests. This is the .NET developer acceptance checklist; client acceptance remains to be performed.

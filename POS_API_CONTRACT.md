# Offline POS API Contract

This contract is for the .NET WinForms POS application. ERPNext remains the source of truth after sync. The POS may bill offline, but it must sync through these whitelisted Retail app APIs only.

## Authentication

Use an ERPNext API Key and Secret for a user with the `POS Integration User` role.

Send every request over HTTPS in hosted environments.

## Idempotency Rule

Every POS document must carry a globally unique `external_pos_reference`.

Recommended format:

```text
{BRANCH}-{COUNTER}-{yyyyMMdd}-{sequence}
```

Example:

```text
DXB-C01-20260616-000001
```

If a request times out, retry the exact same payload with the same `external_pos_reference`. ERPNext will return `Duplicate` with the existing document name instead of creating another invoice.

## Endpoints

Base format:

```text
/api/method/retail.api.pos_sync.{method_name}
```

### 1. Health Check

```text
GET /api/method/retail.api.pos_sync.health_check?branch=Branch A&counter_code=C01
```

Response:

```json
{
  "status": "OK",
  "company": "My Company",
  "branch": "Branch A",
  "warehouse": "Branch A - WH",
  "cost_center": "Branch A - CC",
  "counter": "Branch A-C01",
  "terminal_id": "TERM-C01",
  "server_time": "2026-06-16 12:00:00"
}
```

### 2. Pull Master Data

```text
GET /api/method/retail.api.pos_sync.get_pos_master_data?branch=Branch A&counter_code=C01&modified_after=2026-06-16 00:00:00
```

Returns items, barcodes, item prices, customers, modes of payment, and active counters for the branch.

### 3. Create Sales Invoice

```text
POST /api/method/retail.api.pos_sync.create_pos_sales_invoice
```

Request:

```json
{
  "external_pos_reference": "BRANCHA-C01-20260616-000001",
  "pos_bill_no": "000001",
  "company": "My Company",
  "branch": "Branch A",
  "counter_code": "C01",
  "cashier": "cashier@example.com",
  "customer": "Walk In Customer",
  "posting_date": "2026-06-16",
  "posting_time": "13:30:00",
  "is_pos": 1,
  "update_stock": 1,
  "items": [
    {
      "item_code": "ITEM-001",
      "barcode": "629000000001",
      "qty": 2,
      "rate": 10,
      "discount_amount": 0
    }
  ],
  "payments": [
    {
      "mode_of_payment": "Cash",
      "amount": 20,
      "reference_no": "CASH-000001"
    }
  ]
}
```

Success:

```json
{
  "status": "Success",
  "invoice_name": "ACC-SINV-2026-00001",
  "docstatus": 1,
  "grand_total": 20,
  "outstanding_amount": 0
}
```

Duplicate retry:

```json
{
  "status": "Duplicate",
  "invoice_name": "ACC-SINV-2026-00001",
  "docstatus": 1,
  "grand_total": 20,
  "outstanding_amount": 0
}
```

### 4. Create Payment Entry

Use this for later credit customer collection, not normal cash/card POS sales.

```text
POST /api/method/retail.api.pos_sync.create_pos_payment_entry
```

Request:

```json
{
  "external_pos_reference": "BRANCHA-C01-PAY-20260616-000001",
  "sales_invoice": "ACC-SINV-2026-00001",
  "branch": "Branch A",
  "counter_code": "C01",
  "payment_mode": "Cash",
  "paid_amount": 50,
  "posting_date": "2026-06-16",
  "reference_no": "CASH-COLLECTION-000001"
}
```

### 5. Create Return Invoice

```text
POST /api/method/retail.api.pos_sync.create_pos_return_invoice
```

Request:

```json
{
  "external_pos_reference": "BRANCHA-C01-RET-20260616-000001",
  "original_external_pos_reference": "BRANCHA-C01-20260616-000001",
  "branch": "Branch A",
  "counter_code": "C01",
  "customer": "Walk In Customer",
  "posting_date": "2026-06-16",
  "items": [
    {
      "item_code": "ITEM-001",
      "qty": 1,
      "rate": 10
    }
  ],
  "payments": [
    {
      "mode_of_payment": "Cash",
      "amount": 10
    }
  ]
}
```

The POS sends positive quantities. ERPNext converts them into return quantities.

### 6. Get Sync Status

```text
POST /api/method/retail.api.pos_sync.get_sync_status
```

Request:

```json
{
  "external_references": [
    "BRANCHA-C01-20260616-000001",
    "BRANCHA-C01-20260616-000002"
  ]
}
```

## .NET Developer Rules

1. Generate `external_pos_reference` locally before saving a bill.
2. Never reuse an external reference for another bill.
3. Store every bill in a local sync queue.
4. Retry failed or timed-out syncs with the same payload.
5. Treat `Duplicate` as a successful sync if ERPNext returns a document name.
6. Do not call ERPNext's generic Sales Invoice REST insert endpoint.
7. Pull master data using `modified_after`.
8. Store ERPNext document names after sync.
9. Send branch and counter code on every write request.
10. For returns, send the original external reference or original ERPNext invoice name.
11. Keep failed syncs visible to the cashier/admin until corrected.

## ERPNext Setup Required

Create one `POS Branch Counter` per physical billing counter.

Each counter must map to:

```text
Company
Branch
Warehouse
Cost Center
Counter Code
Counter Name
Default Customer
Cash Account
Card Account
POS Profile
Active
```

The .NET app should not decide warehouse or cost center by itself. It sends branch and counter code; ERPNext resolves the correct mapping.

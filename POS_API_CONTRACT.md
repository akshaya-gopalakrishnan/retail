# Offline POS API Contract

**Audience:** .NET offline POS developers.

This is the supported integration contract for the local .NET POS. Do not use ERPNext generic REST insert/update APIs for POS invoices, payments, shifts, customers, stock, or day closing.

## 1. ERPNext Setup Required Before .NET Configuration

For each physical POS counter, ERPNext must have one active `POS Branch Counter`.

Example for one branch with 100 counters:

| ERPNext Setup | Quantity | Example |
|---|---:|---|
| Company | 1 | `nesto` |
| Branch | 1 | `Karama` |
| Warehouse | 1 or more | `Stores - N` |
| Cost Center | 1 or more | `Main - N` |
| POS Profile | Usually 1 per branch/setup | `Karama POS` |
| POS Branch Counter | 100 | `C001` to `C100` |
| Device/API User | Recommended 1 per branch; optional 1 per counter for stricter isolation | `pos.karama.api@company.com` |
| Cashier Employee | As many as required | `HR-EMP-00001` |

Each `POS Branch Counter` must be configured with:

```text
Company
Branch
Warehouse
Cost Center
Counter Code
Counter Name
Terminal ID
POS Profile
Default Customer
Cash Account
Card Account
Allow Offline Sync = 1
Integration User = branch/counter API user
```

The .NET POS does not choose company, warehouse, cost center, POS profile, or payment accounts. ERPNext resolves them from `branch + counter_code`.

If using one API user per branch, set the same integration user on every `POS Branch Counter` in that branch. Reports and postings still remain counter-wise because .NET sends `counter_code`, `terminal_id`, `cashier_employee`, `cashier_shift`, and `counter_session`.

## 2. What .NET Needs Per Counter

Each installed POS counter must store these local configuration values:

```text
ErpBaseUrl
Branch
CounterCode
TerminalId
ApiKey
ApiSecret
```

Example:

```text
ErpBaseUrl = https://erp.company.com
Branch = Karama
CounterCode = C001
TerminalId = T001
ApiKey/ApiSecret = API credentials of pos.karama.api@company.com
```

ERPNext is the printer assignment master. .NET should pull `printer_name` from the counter master data and use the matching local Windows printer for that terminal.

Cashier is not the API user. Cashier is selected/login inside .NET POS as an ERPNext `Employee`.

```text
Counter/device identity = API user
Cashier identity = Employee
```

## 3. Transport And Authentication

```text
https://{erp-host}/api/method/retail.api.pos_sync.{method_name}
Authorization: token {api_key}:{api_secret}
Content-Type: application/json
Accept: application/json
```

All examples below show the Frappe `message` payload only:

```json
{ "message": { "status": "Success" } }
```

Use HTTPS outside local testing.

## 4. Idempotency And References

Every syncable transaction must have a unique `external_pos_reference` generated before saving locally.

Format:

```text
{BRANCH}-{COUNTER}-{TERMINAL}-{TYPE}-{yyyyMMdd}-{sequence}
```

Examples:

```text
KARAMA-C001-T001-SHIFTOPEN-20260625-000001
KARAMA-C001-T001-S-20260625-000002
KARAMA-C001-T001-R-20260625-000003
KARAMA-C001-T001-BREAK-20260625-000004
KARAMA-C002-T002-RESUME-20260625-000005
KARAMA-C002-T002-SHIFTCLOSE-20260625-000006
```

Rules:

- Never reuse an `external_pos_reference` for a different business transaction.
- If timeout/no response occurs, call `get_sync_status` with the same reference before retrying.
- Retry the exact same payload for the same reference.
- Do not generate replacement references to bypass errors.

## 5. Cashier Shift Model

The current required flow is:

```text
POS Cashier Shift   = cashier cash responsibility
POS Counter Session = where that cashier is currently billing
POS Opening Entry   = ERPNext session created per counter session
POS Closing Entry   = ERPNext reconciliation per counter session
POS Branch Day Closing = manager final branch/date close
```

Rules:

- One cashier can have only one `Open` or `Paused` cashier shift.
- One counter can have only one active counter session.
- A cashier can pause/release one counter and resume the same shift on another counter.
- Every invoice must include `cashier_employee`, `cashier_shift`, and `counter_session`.
- Day closing blocks further POS sync for that branch/business date.
- To correct a closed day, manager must cancel day closing with reason, reopen the cashier shift with reason, correct/close again, then submit day closing again.

## 6. Startup APIs

### Health Check

```text
GET /api/method/retail.api.pos_sync.health_check?branch=Karama&counter_code=C001
```

Returns server time and counter mapping:

```json
{
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
```

### Pull Master Data

```text
GET /api/method/retail.api.pos_sync.get_pos_master_data?branch=Karama&counter_code=C001&modified_after=2026-06-25%2000:00:00
```

Omit `modified_after` for first full pull. Save returned `server_time` after the full response is stored locally.

Main collections returned:

```text
counter
tax_config
items
item_barcodes
packing_details
item_prices
customers
cashiers
modes_of_payment
counters
```

Use ERPNext `server_time` as the next `modified_after`; do not rely on Windows time.

Item sync behavior:

- `items` includes both active and disabled items.
- `items` includes audit fields: `created_by`, `created_on`, `modified_by`, `modified_on`. The existing `modified` field is still returned for incremental sync compatibility.
- `items` includes POS item flags: `is_scalable_item`, `scale_barcode_type`, `is_open_price`, and `is_fast_plu_item`. `is_scalable_item` comes from Item's `Scale Item`; `scale_barcode_type` comes from Item's `Scale Barcode Type`; `is_open_price` comes from Item's `Open Price`; `is_fast_plu_item` comes from Item's `Fast PLU Item`.
- .NET should show a main item in the fast PLU item list when the item row has `is_fast_plu_item = 1`.
- .NET should use only `is_scalable_item` and `scale_barcode_type` for scale-item handling. ERPNext does not send PLU, prefix, scale UOM, scale format, or scale unit code in POS master sync.
- `scale_barcode_type` values are `Price`, `Weight`, `Quantity`, or `Weight+UnitPrice`.
- .NET should upsert item rows by `item_code` / `name`.
- Each item row includes `packings`, containing that Item's `Retail Packing Detail` child rows from `custom_retail_packing_detail`.
- `packing_details` is still returned as a flat compatibility package for older POS sync clients.
- .NET should link each packing row to its parent item using `item_code`.
- `name` is ERPNext's internal child-row id. Use `packing_code` as the readable business key when present; otherwise fall back to `name` or `item_code + idx`.
- Use `packing_name` as the POS display name for packing rows. Example: `Water - Box x24`, so cashiers can distinguish base UOM, box-24, and box-14 entries during search/sale.
- Packing rows include `packing_code`, `packing_name`, `is_fast_plu_item`, `barcode`, `barcode_type`, `uom`, `conversion_factor`, purchase/selling rates, VAT split fields, `packing_margin`, and `modified`.
- .NET should show a packing row in the fast PLU item list when that packing row has `is_fast_plu_item = 1`. This is separate from the parent Item's `is_fast_plu_item`.
- If an item row has `disabled = 1`, mark the local POS item inactive/hidden and do not allow it for new sales.
- Do not delete old local invoice rows that used this item; historical invoices must continue to display correctly.
- `modified_after` returns only rows changed after that ERPNext server timestamp, including items that were disabled after the previous sync and packing rows changed after the previous sync.

Cashiers are returned from ERPNext `Employee` records. .NET should store the returned `name` value locally and send it as `cashier_employee` in all cashier shift and invoice APIs. For compatibility, ERPNext also accepts the cashier's `employee`, `employee_number`, `attendance_device_id`, `user_id`, or `cell_number` and resolves it to the Employee document name.

`designation` is returned from Employee and is also exposed as `operator_group`, for example Cashier, Waiter, Delivery Person, or Supervisor.

For cashier login, .NET should use `login_id` from the cashier row. ERPNext does not send passwords or raw quick PINs in master sync.

Cashier rows include `quick_pin_hash` and `quick_pin_salt` when configured. For offline login, hash the entered PIN as SHA256 of `{quick_pin_salt}:{entered_pin}` and compare with `quick_pin_hash`. Online verification is also available through `verify_cashier_quick_pin`.

System Manager can set/reset a cashier PIN with `set_cashier_quick_pin`.

ERPNext UI setup:

- On `Employee`, enable `Allow POS Login`, select `POS Login User`, and enter `Set POS Quick PIN`.
- On `User`, enable `Allow POS Login`, select `POS Cashier Employee`, and enter `Set POS Quick PIN`.
- Both forms update the same Employee POS login hash/salt. The raw PIN is never stored.

Recommended master sync schedule:

- First install/startup: call without `modified_after` and store the full response locally.
- Normal online mode: call with the last saved ERPNext `server_time` every 2-3 minutes.
- Offline recovery: when internet returns, immediately run the same incremental pull before sending queued transactions.
- .NET manual sync button: run the same API immediately.
- ERPNext manual action: use it only to mark/check that POS master sync is needed unless the branch has a reachable .NET service. The reliable transfer direction is .NET pulling from ERPNext.

## 7. Cashier Shift APIs

### Check Cashier/Counter Status

```text
POST /api/method/retail.api.pos_sync.get_cashier_shift_status
```

```json
{
  "branch": "Karama",
  "counter_code": "C001",
  "cashier_employee": "HR-EMP-00001"
}
```

Use `recommended_action` to decide the .NET screen:

```text
OpenNewShift
ContinueSession
TransferOrResume
CounterBusy
```

### Open Cashier Shift

```text
POST /api/method/retail.api.pos_sync.open_cashier_shift
```

```json
{
  "external_pos_reference": "KARAMA-C001-T001-SHIFTOPEN-20260625-000001",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "HR-EMP-00001",
  "business_date": "2026-06-25",
  "opening_balances": [
    { "mode_of_payment": "Cash", "opening_amount": 100 }
  ]
}
```

Response:

```json
{
  "status": "Success",
  "cashier_shift": "POS-CSH-2026-00001",
  "counter_session": "POS-CSES-2026-00001",
  "pos_opening_entry": "POS-OPE-2026-00001",
  "cashier_employee": "HR-EMP-00001",
  "counter": "Karama-C001",
  "counter_code": "C001"
}
```

Save `cashier_shift`, `counter_session`, and `pos_opening_entry` locally.

### Pause / Break

Use this when the cashier goes for break and the counter must be available to someone else.

```text
POST /api/method/retail.api.pos_sync.pause_cashier_shift
```

```json
{
  "external_pos_reference": "KARAMA-C001-T001-BREAK-20260625-000004",
  "cashier_shift": "POS-CSH-2026-00001",
  "counter_session": "POS-CSES-2026-00001",
  "business_date": "2026-06-25",
  "release_counter": 1,
  "closing_balances": [
    { "mode_of_payment": "Cash", "closing_amount": 350 }
  ]
}
```

If `release_counter = 1`, ERPNext closes the current counter session and frees the counter.

### Resume / Transfer Cashier Shift

Use this when the same cashier returns to the same counter or moves to another counter.

```text
POST /api/method/retail.api.pos_sync.resume_cashier_shift
```

```json
{
  "external_pos_reference": "KARAMA-C002-T002-RESUME-20260625-000005",
  "branch": "Karama",
  "counter_code": "C002",
  "pos_terminal_id": "T002",
  "cashier_shift": "POS-CSH-2026-00001",
  "business_date": "2026-06-25",
  "opening_balances": [
    { "mode_of_payment": "Cash", "opening_amount": 350 }
  ]
}
```

Response returns the active/new `counter_session` and `pos_opening_entry`. Use those values on the next invoices.

### Cash In / Cash Out

Use this for petty cash, counter expenses, cash taken from the drawer, or cash added to the drawer. Do not send these rows as POS invoice payments.

```text
POST /api/method/retail.api.pos_sync.create_pos_cash_movement
```

```json
{
  "external_pos_reference": "KARAMA-C001-T001-CASHOUT-20260625-000010",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "HR-EMP-00001",
  "cashier_shift": "POS-CSH-2026-00001",
  "counter_session": "POS-CSES-2026-00001",
  "movement_type": "Cash Out",
  "amount": 100,
  "description": "Petty cash expense"
}
```

`movement_type` must be `Cash In` or `Cash Out`. ERPNext stores the row cashier-wise against `cashier_shift` and `counter_session`. The `description` is stored as the POS reason/description.

`cash_movement` in the response is the ERPNext unique document ID. `external_pos_reference` is the POS/.NET unique transaction ID echoed back for local reconciliation and duplicate handling.

Response:

```json
{
  "status": "Success",
  "cash_movement": "POS-CMOV-2026-00001",
  "external_pos_reference": "KARAMA-C001-T001-CASHOUT-20260625-000010",
  "cashier_shift": "POS-CSH-2026-00001",
  "counter_session": "POS-CSES-2026-00001",
  "movement_type": "Cash Out",
  "amount": 100,
  "cash_in_amount": 0,
  "cash_out_amount": 100,
  "expected_cash": 350
}
```

### Close Cashier Shift

```text
POST /api/method/retail.api.pos_sync.close_cashier_shift
```

```json
{
  "external_pos_reference": "KARAMA-C002-T002-SHIFTCLOSE-20260625-000006",
  "cashier_shift": "POS-CSH-2026-00001",
  "business_date": "2026-06-25",
  "closing_balances": [
    { "mode_of_payment": "Cash", "closing_amount": 900 }
  ]
}
```

ERPNext calculates:

```text
expected_cash = opening cash + synced cash POS invoice payments + cash in - cash out
variance = closing cash - expected cash
```

## 8. Sales And Return APIs

### Create POS Invoice

```text
POST /api/method/retail.api.pos_sync.create_pos_invoice
```

```json
{
  "external_pos_reference": "KARAMA-C001-T001-S-20260625-000002",
  "pos_bill_no": "000002",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier": "Cashier Display Name",
  "cashier_employee": "HR-EMP-00001",
  "cashier_shift": "POS-CSH-2026-00001",
  "counter_session": "POS-CSES-2026-00001",
  "customer": "Walk In Customer",
  "posting_date": "2026-06-25",
  "posting_time": "13:30:00",
  "pos_shift_no": "POS-OPE-2026-00001",
  "pos_local_created_at": "2026-06-25 13:30:00",
  "update_stock": 1,
  "vat_amount": 1.0,
  "items": [
    { "item_code": "ITEM-001", "barcode": "629000000001", "qty": 2, "rate": 10.0, "discount_amount": 0.0 }
  ],
  "payments": [
    { "mode_of_payment": "Cash", "amount": 21.0, "reference_no": "CASH-000002" }
  ]
}
```

Required together:

```text
cashier_employee
cashier_shift
counter_session
```

ERPNext rejects invoice sync if the cashier shift/session is not active on that counter.

Important:

- `vat_amount` is mandatory.
- Send `vat_amount = 0` if no tax applies.
- Credit POS sales are not supported here.
- Client must not send ledger accounts, warehouse, cost center, company, or POS profile.
- `pos_shift_no` should be the returned ERPNext `pos_opening_entry`.

Response:

```json
{
  "status": "Success",
  "pos_invoice_name": "ACC-PSINV-2026-00001",
  "invoice_name": "ACC-PSINV-2026-00001",
  "doctype": "POS Invoice",
  "docstatus": 1,
  "grand_total": 21.0,
  "outstanding_amount": 0.0
}
```

### Create POS Return

```text
POST /api/method/retail.api.pos_sync.create_pos_return_invoice
```

```json
{
  "external_pos_reference": "KARAMA-C001-T001-R-20260625-000003",
  "original_external_pos_reference": "KARAMA-C001-T001-S-20260625-000002",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "HR-EMP-00001",
  "cashier_shift": "POS-CSH-2026-00001",
  "counter_session": "POS-CSES-2026-00001",
  "customer": "Walk In Customer",
  "posting_date": "2026-06-25",
  "pos_shift_no": "POS-OPE-2026-00001",
  "vat_amount": -0.5,
  "items": [
    { "item_code": "ITEM-001", "qty": 1, "rate": 10.0 }
  ],
  "payments": [
    { "mode_of_payment": "Cash", "amount": 10.5 }
  ]
}
```

Send positive item/payment amounts. ERPNext converts them to negative return values.

Return dependency:

```text
original sale must sync first
```

### Create Payment Entry

Normally not required for paid POS invoices because `create_pos_invoice` submits invoice payments in the same payload. Use this only for a separate ERPNext `Sales Invoice` payment sync if your .NET flow supports that.

```text
POST /api/method/retail.api.pos_sync.create_pos_payment_entry
```

```json
{
  "external_pos_reference": "KARAMA-C001-T001-PAY-20260625-000004",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "HR-EMP-00001",
  "cashier_shift": "POS-CSH-2026-00001",
  "counter_session": "POS-CSES-2026-00001",
  "sales_invoice": "ACC-SINV-2026-00001",
  "mode_of_payment": "Cash",
  "reference_no": "CASH-000004",
  "posting_date": "2026-06-25"
}
```

## 9. Customer And Stock APIs

### Customer Upsert

```text
POST /api/method/retail.api.pos_sync.upsert_customer
```

```json
{
  "external_customer_id": "CUST-C001-000001",
  "branch": "Karama",
  "counter_code": "C001",
  "customer_name": "Customer Name",
  "customer_group": "All Customer Groups",
  "territory": "All Territories",
  "mobile_no": "9715XXXXXXXX",
  "email_id": "customer@example.com",
  "tax_id": ""
}
```

Matching is by `external_customer_id`.

### Customer Balance Pull

```text
GET /api/method/retail.api.pos_sync.get_customer_balances?company=nesto&from_date=2026-01-01&to_date=2026-07-22&include_zero_balance=1
```

Use this API when .NET needs customer-wise contact and ledger balance data.

Query parameters:

| Parameter | Required | Notes |
|---|---|---|
| `company` | Yes, unless the site has only one company | ERPNext Company name |
| `from_date` | No | Defaults to fiscal year start date |
| `to_date` | No | Defaults to ERPNext server date |
| `customer` | No | ERPNext Customer ID for one customer only |
| `include_zero_balance` | No | Send `1` to include active customers with no ledger balance/activity |

Response:

```json
{
  "status": "Success",
  "company": "nesto",
  "from_date": "2026-01-01",
  "to_date": "2026-07-22",
  "count": 1,
  "data": [
    {
      "customer": "CUST-0001",
      "customer_name": "Customer Name",
      "email": "customer@example.com",
      "phone": "9715XXXXXXXX",
      "opening_balance": 1000.0,
      "transaction_amount": 500.0,
      "payment_amount": 300.0,
      "current_balance": 1200.0,
      "address": "Dubai, UAE",
      "address_id": "ADDR-0001"
    }
  ]
}
```

Amount fields are calculated from ERPNext Customer Ledger Summary:

| API field | Meaning |
|---|---|
| `opening_balance` | Balance before `from_date` |
| `transaction_amount` | Customer invoiced/debit amount for the selected date range |
| `payment_amount` | Customer paid/credit amount for the selected date range |
| `current_balance` | Closing balance up to `to_date` |

### Warehouse Stock Snapshot

```text
POST /api/method/retail.api.pos_sync.get_warehouse_stock_snapshot
```

```json
{
  "branch": "Karama",
  "counter_code": "C001",
  "item_codes": ["ITEM-001"]
}
```

Returned stock rows include both `actual_qty` and `current_stock`; .NET can use `current_stock` for the POS item stock display.

Stock snapshot is advisory. ERPNext still validates at invoice submission.

## 10. Sync Status And Queue Helpers

### Sync Status

```text
POST /api/method/retail.api.pos_sync.get_sync_status
```

```json
{
  "external_references": [
    "KARAMA-C001-T001-S-20260625-000002"
  ]
}
```

Use this after timeouts before retrying.

### Queue Dependencies

```text
POST /api/method/retail.api.pos_sync.get_queue_dependencies
```

Payload contains branch/counter and local queue rows:

```json
{
  "branch": "Karama",
  "counter_code": "C001",
  "queue": [
    {
      "external_pos_reference": "KARAMA-C001-T001-R-20260625-000003",
      "original_external_pos_reference": "KARAMA-C001-T001-S-20260625-000002"
    }
  ]
}
```

### Queue Error Audit

```text
POST /api/method/retail.api.pos_sync.ingest_queue_errors
```

Use this to send local queue failures to ERPNext audit logs. It does not mark local rows successful.

## 11. Day Closing APIs

### Create / Refresh Day Closing

```text
POST /api/method/retail.api.pos_sync.make_branch_day_closing
```

```json
{
  "branch": "Karama",
  "business_date": "2026-06-25"
}
```

ERPNext creates or returns the single non-cancelled `POS Branch Day Closing` for that branch/date.

One branch/date can have only one non-cancelled day closing.

### Submit Day Closing

```text
POST /api/method/retail.api.pos_sync.submit_branch_day_closing
```

```json
{
  "branch": "Karama",
  "business_date": "2026-06-25"
}
```

Submit is blocked when:

```text
open_shift_count > 0
active_counter_session_count > 0
no cashier shifts exist
```

After submit, POS sync for that branch/date is blocked.

### Cancel Day Closing For Correction

```text
POST /api/method/retail.api.pos_sync.cancel_branch_day_closing
```

```json
{
  "branch": "Karama",
  "business_date": "2026-06-25",
  "cancel_reason": "Cash count correction required"
}
```

Reason is mandatory.

### Reopen Cashier Shift For Correction

```text
POST /api/method/retail.api.pos_sync.reopen_cashier_shift
```

```json
{
  "cashier_shift": "POS-CSH-2026-00001",
  "business_date": "2026-06-25",
  "reopen_reason": "Wrong closing cash entered"
}
```

Rules:

- Day closing must be cancelled first.
- Only a closed cashier shift can be reopened.
- Reopen audit is stored on the cashier shift.
- Reopened shift becomes `Paused`.
- Manager/cashier must close it again using `close_cashier_shift`.
- Then refresh and submit day closing again.

## 12. Legacy APIs

These methods exist only for backward compatibility and should not be used for new .NET development:

```text
open_pos_shift
close_pos_shift
create_pos_sales_invoice
```

New development must use:

```text
open_cashier_shift
pause_cashier_shift
resume_cashier_shift
close_cashier_shift
create_pos_invoice
create_pos_return_invoice
create_pos_cash_movement
make_branch_day_closing
submit_branch_day_closing
cancel_branch_day_closing
reopen_cashier_shift
```

## 13. Local .NET Database Requirements

The .NET POS needs a local transactional database. SQLite or SQL Server LocalDB is fine.

### Local Configuration Table

Store one row per installed POS:

```text
ErpBaseUrl
Branch
CounterCode
TerminalId
ApiKey
ApiSecret
LastMasterSyncServerTime
```

### Cashier Master Cache

Cache ERPNext Employee/cashier data or maintain a local cashier table synced from ERPNext/custom export:

```text
CashierEmployee
CashierName
CashierCode/PIN/CardNo
IsActive
LastUpdated
```

Normal cashiers do not need ERPNext user accounts. They are Employees.

### Local Shift Tables

Recommended:

```text
CashierShiftLocalId
CashierEmployee
Branch
BusinessDate
Status
OpeningAmount
ExpectedCash
ClosingAmount
Variance
ExternalOpenReference
ExternalCloseReference
ErpCashierShift
CurrentCounterSession
CurrentPosOpeningEntry
OpenedAt
ClosedAt
ReopenCount
LastSyncStatus
```

Counter session table:

```text
CounterSessionLocalId
CashierShiftLocalId
CounterCode
TerminalId
Status
ExternalOpenOrResumeReference
ExternalPauseReference
ErpCounterSession
ErpPosOpeningEntry
ErpPosClosingEntry
StartedAt
EndedAt
```

### Local Invoice Tables

At minimum:

```text
LocalInvoiceId
ExternalPosReference
PosBillNo
Branch
CounterCode
TerminalId
BusinessDate
CashierEmployee
ErpCashierShift
ErpCounterSession
ErpPosOpeningEntry
Customer
PostingDate
PostingTime
VatAmount
GrandTotal
IsReturn
OriginalExternalPosReference
SyncStatus
ErpDocumentName
LastError
CreatedAt
SyncedAt
```

Invoice item rows:

```text
LocalInvoiceId
ItemCode
Barcode
Qty
Rate
DiscountAmount
TaxAmount if locally calculated/displayed
```

Payment rows:

```text
LocalInvoiceId
ModeOfPayment
Amount
ReferenceNo
```

Cash movement rows:

```text
CashMovementLocalId
ExternalPosReference
Branch
CounterCode
TerminalId
BusinessDate
CashierEmployee
CashierShiftLocalId
ErpCashierShift
ErpCounterSession
MovementType
Amount
Description
CreatedAt
SyncStatus
ErpDocumentName
LastError
SyncedAt
```

### Local Sync Queue

Use an immutable queued payload table:

| Column | Purpose |
|---|---|
| `ExternalPosReference` unique | Idempotency key |
| `DocumentType` | `ShiftOpen`, `ShiftPause`, `ShiftResume`, `Sale`, `Return`, `ShiftClose`, `Customer`, `DayClose`, `Correction` |
| `DependencyReference` | Opening reference or original sale reference |
| `PayloadJson` | Exact JSON body to retry |
| `Status` | `Pending`, `Processing`, `Synced`, `DuplicateSynced`, `Retry`, `Failed`, `NeedsReview`, `BlockedDependency` |
| `AttemptCount` | Retry count |
| `NextAttemptAt` | Retry scheduling |
| `LastAttemptAt` | Last attempt timestamp |
| `LastError` | Last ERP/network error |
| `ErpDocumentName` | Returned ERPNext document |
| `SyncedOn` | Sync completion timestamp |

Queue order:

```text
open_cashier_shift
sale / return
pause/resume if needed
close_cashier_shift
day closing, if manager action is done from .NET
```

Returns must wait for original sale sync.

## 14. Go-Live Checklist For .NET Team

- Configure unique `CounterCode` and `TerminalId` per machine.
- Use the counter/device API key, not cashier credentials.
- Cashier login must map to ERPNext `Employee`.
- Store `cashier_shift`, `counter_session`, and `pos_opening_entry` after shift open/resume.
- Send those three values on every invoice and return.
- Keep the original queued JSON immutable.
- Use `get_sync_status` after timeout before retry.
- Do not submit day closing until all local queue rows for the business date are synced.
- After ERPNext day closing is submitted, block local billing for that business date.

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
| Device/API User | Recommended 1 per counter | `pos.c001@company.com` |
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
Integration User = counter/device API user
```

The .NET POS does not choose company, warehouse, cost center, POS profile, or payment accounts. ERPNext resolves them from `branch + counter_code`.

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
ApiKey/ApiSecret = API credentials of pos.c001@company.com
```

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
item_prices
customers
cashiers
modes_of_payment
counters
```

Use ERPNext `server_time` as the next `modified_after`; do not rely on Windows time.

Cashiers are returned from ERPNext `Employee` records. .NET must store the returned `name`/`employee` value locally and send it as `cashier_employee` in all cashier shift and invoice APIs.

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
expected_cash = opening cash + synced cash POS invoice payments
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

# POS API Contract — .NET Guide

All POS API examples are in this file, including day and payment corrections.
Examples use sample IDs and amounts. Replace them with your saved values.
Responses show the fields needed by POS; ERP may return more fields.
Development site: `retail-test.localhost`.

## Connection and basic rules

```text
Base URL: https://<erp-address>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
Accept: application/json
```

- Configure the branch, counter, terminal and API credentials before first use. Download masters before working offline.
- Use downloaded ERP IDs exactly as returned. ERP chooses the company, warehouse, accounts and POS profile from the counter.
- Save each request before sending. On timeout, retry the same JSON and reference. Never change a saved bill to retry it.
- Create a different `external_pos_reference` for each new action (maximum 140 characters). Keep the same shift reference when changing counters; create a new session reference when moving to a new session.
- Send the cashier who performed the action and their shift/session. Keep the original sale reference separately on returns and collections.
- Keep the original business date and bill time when sending later. Use decimal values for money. Downloaded selling prices include VAT.
- Prefer sending openings before bills and closing actions. Completed sales, returns and exchanges are accepted in any order; ERP keeps dependencies and recovers them internally. Collections and lifecycle actions retain their existing dependency checks. Close the day after every counter has sent its work and closed its shifts.
- Save returned IDs outside the saved request. `docstatus: 1` means submitted. Check the response before marking an action complete.
- Replies are inside `message`, as shown below. HTTP 200 alone does not mean success. `duplicate: true` or `status: "Duplicate"` means a previous successful request was found.

## Startup and login
### Check connection

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

### Download masters

`GET /api/method/retail.api.pos_sync.get_pos_master_data?branch=Karama&counter_code=C001`

Add `modified_after=2026-09-30%2009:00:00` for changes since the last saved `server_time`. Save the time only after saving the whole reply. Empty lists below are examples.

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "status": "Success",
    "server_time": "2026-09-30 09:00:00",
    "counter": {
      "name": "Karama-C001",
      "counter_code": "C001",
      "terminal_id": "T001",
      "printer_name": "Receipt Printer 1"
    },
    "tax_config": {"tax_template": "<tax template>", "taxes": []},
    "bill_format": {
      "address": "Dubai",
      "phone_number": "",
      "email_id": "",
      "tax_id": "",
      "h1": "Store Name",
      "h2": "",
      "h3": "",
      "h4": "",
      "h5": "",
      "f1": "Thank you",
      "f2": "",
      "f3": "",
      "f4": "",
      "f5": ""
    },
    "items": [],
    "item_barcodes": [],
    "packing_details": [],
    "item_prices": [],
    "scale_barcode_formats": [],
    "gift_voucher_promotions": [],
    "customers": [],
    "operators": [],
    "modes_of_payment": [
      {
        "name": "Credit Note",
        "type": "Credit Note",
        "enabled": 1,
        "modified": "2026-09-30 09:00:00",
        "is_settlement": 1,
        "settlement_type": "Credit Note Redeemed"
      },
      {
        "name": "Voucher",
        "type": "Voucher",
        "enabled": 1,
        "modified": "2026-09-30 09:00:00"
      },
      {
        "name": "Cancelled",
        "type": "Cancelled",
        "enabled": 1,
        "modified": "2026-09-30 09:00:00"
      },
      {
        "name": "Customer",
        "type": "Customer",
        "enabled": 1,
        "modified": "2026-09-30 09:00:00"
      }
    ],
    "counters": []
  }
}
```

Use `operators` for cashiers. Missing or false `privileges` means the action is not allowed. Use `printer_name` for the local printer. Empty bill-format values clear old values.

`modes_of_payment` includes the POS options `Credit Note`, `Voucher`, and
`Cancelled`, and `Customer` in every full or changes-only reply, alongside ERP payment modes.
Each option's `type` matches its name exactly; .NET can identify it using `type`.
Their `modified` is the reply-time timestamp. For `Credit Note`, `is_settlement: 1` identifies a
settlement option; when selected, send the credit reference and amount in
`credit_note_redemptions`, not as a cash/card row in `payments`. No ERP Mode of
Payment record or payment account is required for this option.

`Voucher` uses the existing gift-voucher approval and `voucher_redemption` sale
flow. `Cancelled` is a POS cancellation/status option, not a monetary tender;
its presence does not introduce a bill-cancellation API. Do not send either
option as a cash/card payment row or include it in counted cash.

`Customer` identifies the customer-credit option in POS. Send the customer's ERP
ID in `customer` and the unpaid bill amount in `credit_sale_amount`; do not send
`Customer` as a cash/card payment row.

Keep item/packing `disabled`, `is_fast_plu_item`, barcode, UOM, `conversion_factor`, `current_stock`, selling rates and VAT fields. Use `packing_name` for display. Selling rates include VAT; do not add VAT again.

Save changed records without deleting records missing from a changes-only reply. Replace each returned item's full `packings` list and the full `scale_barcode_formats` list. Refresh all masters regularly because permission and customer-balance changes may not appear in a changes-only download.

### Set cashier PIN

`POST /api/method/retail.api.pos_sync.set_cashier_quick_pin`

System Manager only. Keep PINs as text so leading zeros remain.

Request JSON:

```json
{"cashier_employee": "E-1", "quick_pin": "1234"}
```

Response example:

```json
{"message": {"status": "Success", "cashier_employee": "E-1"}}
```

### Check cashier PIN

`POST /api/method/retail.api.pos_sync.verify_cashier_quick_pin`

Failed PIN: `status: "Failed", verified: 0`. Offline check: SHA256 of UTF-8 `quick_pin_salt:entered_pin`, compared with downloaded `quick_pin_hash`. Do not save the plain PIN.

Request JSON:

```json
{"login_id": "1001", "quick_pin": "1234"}
```

Response example:

```json
{"message": {"status": "Success", "verified": 1, "cashier_employee": "E-1"}}
```

## Cashier shifts and cash drawer

### Check cashier and counter

`POST /api/method/retail.api.pos_sync.get_cashier_shift_status`

Check `can_use_counter` as well as `recommended_action`. Other actions: `ContinueSession`, `TransferOrResume`, `CounterBusy`.

Request JSON:

```json
{"branch": "Karama", "counter_code": "C001", "cashier_employee": "E-1"}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "cashier_employee": "E-1",
    "cashier_name": "Cashier Name",
    "cashier_shift": null,
    "cashier_active_counter_session": null,
    "counter_active_session": null,
    "can_use_counter": true,
    "recommended_action": "OpenNewShift"
  }
}
```

### Open shift

`POST /api/method/retail.api.pos_sync.open_cashier_shift`

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-SHIFTOPEN-20260625-000001",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "opened_at": "2026-06-25 09:00:00",
  "opening_balances": [{"mode_of_payment": "Cash", "opening_amount": 100}]
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "cashier_shift": "PSH-1",
    "counter_session": "PCS-1",
    "pos_opening_entry": "POE-1",
    "cashier_employee": "E-1",
    "counter": "Karama-C001",
    "counter_code": "C001"
  }
}
```

### Pause or break

`POST /api/method/retail.api.pos_sync.pause_cashier_shift`

Use `release_counter: 1` to free the counter; `0` keeps it assigned.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-BREAK-20260625-000004",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "paused_at": "2026-06-25 14:00:00",
  "release_counter": 1,
  "closing_balances": [{"mode_of_payment": "Cash", "closing_amount": 350}]
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "cashier_shift": "PSH-1",
    "counter_session": "PCS-1",
    "counter_released": true,
    "pos_closing_entry": "PCE-1"
  }
}
```

### Resume or change counter

`POST /api/method/retail.api.pos_sync.resume_cashier_shift`

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C002-T002-RESUME-20260625-000005",
  "branch": "Karama",
  "counter_code": "C002",
  "pos_terminal_id": "T002",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C002-T002-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "resumed_at": "2026-06-25 15:00:00",
  "opening_balances": [{"mode_of_payment": "Cash", "opening_amount": 350}]
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "action": "Resumed",
    "cashier_shift": "PSH-1",
    "counter_session": "PCS-2",
    "pos_opening_entry": "POE-2",
    "counter": "Karama-C002",
    "counter_code": "C002"
  }
}
```

### Cash in or cash out

`POST /api/method/retail.api.pos_sync.create_pos_cash_movement`

Use `movement_type: "Cash In"` or `"Cash Out"`; amount is positive. Each action needs its own reference.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-CASHOUT-20260625-000010",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "posting_datetime": "2026-06-25 13:45:00",
  "movement_type": "Cash Out",
  "amount": 100,
  "description": "Petty cash expense"
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "cash_movement": "PCM-1",
    "external_pos_reference": "KARAMA-C001-T001-CASHOUT-20260625-000010",
    "cashier_shift": "PSH-1",
    "counter_session": "PCS-1",
    "movement_type": "Cash Out",
    "amount": 100,
    "cash_in_amount": 0,
    "cash_out_amount": 100,
    "expected_cash": 350
  }
}
```

### Close shift

`POST /api/method/retail.api.pos_sync.close_cashier_shift`

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C002-T002-SHIFTCLOSE-20260625-000006",
  "branch": "Karama",
  "counter_code": "C002",
  "pos_terminal_id": "T002",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C002-T002-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "closed_at": "2026-06-25 18:00:00",
  "closing_balances": [{"mode_of_payment": "Cash", "closing_amount": 900}]
}
```

Response example:

```json
{"message": {"status": "Success", "cashier_shift": "PSH-1", "pos_closing_entries": ["PCE-2"]}}
```

## Sales, returns and customer payments

For Payment Entries, send optional `reference_no` to fill **Cheque/Reference No**. This applies to `create_customer_deposit`, `pay_customer_invoice`, `create_pos_payment_entry`, and the `CollectCredit` / `ChangeCollectionMOP` correction actions. If omitted or empty, the existing fallback remains: `external_pos_reference` for the three payment APIs, or `operation_reference` for corrections.

### Send an exchange receipt (sales and returns together)

Use the existing `POST /api/method/retail.api.pos_sync.create_pos_invoice` endpoint. A negative item `qty` selects exchange processing, including receipts containing only returns. Positive quantities are sold; negative quantities are returned. Keep unit `rate` positive (negative legacy return rates are accepted as magnitudes). Send signed line `amount`, final `net_amount` excluding VAT, and `vat_amount`. Header totals must equal the signed lines, after discounts. An invoice discount requires explicit final `net_amount` on every line.

Use a **new** `external_pos_reference` for the entire receipt and retain its normal `pos_bill_no`. Returns support both cases:

- **With the original bill:** send `original_external_pos_reference` on the returned item, or on the header when returns share an original bill. The original submitted sale must belong to the same customer, company and branch. Original item/UOM and ERPNext return quantity limits are validated. A supplied original reference that has not synced is permanently accepted as `Pending Dependency`; ERP posts the exchange after the original arrives. Do not resend or change the completed receipt. An invalid supplied reference is never silently treated as a return without a bill.
- **Without the original bill:** omit `original_external_pos_reference` or send an empty string. ERP creates a standalone return/credit note with no `return_against`. Stock is received using ERPNext's unlinked return valuation rules; the historical sale's cost and quantity limits cannot be verified. An explicit empty reference on an item overrides a header reference, allowing linked and standalone returns in the same receipt.

Example item/payment fields, alongside the usual branch, counter, cashier, date and shift/session fields:

```json
{
  "external_pos_reference": "BRANCH-COUNTER-TERMINAL-EXCHANGE-10",
  "pos_bill_no": "10",
  "original_external_pos_reference": "BRANCH-COUNTER-TERMINAL-SALE-9",
  "items": [
    {"item_code": "MILK", "uom": "Nos", "conversion_factor": 1, "qty": 2, "rate": 10, "rate_includes_vat": 0, "amount": 20, "net_amount": 20, "vat_rate": 0, "vat_amount": 0},
    {"item_code": "MILK", "uom": "Nos", "conversion_factor": 1, "qty": -1, "rate": 10, "rate_includes_vat": 0, "amount": -10, "net_amount": -10, "vat_rate": 0, "vat_amount": 0}
  ],
  "grand_total": 10,
  "vat_amount": 0,
  "payments": [{"mode_of_payment": "CARD", "amount": 10}]
}
```

Positive net bills collect money; negative bills refund money. Send only the actual net tender in `payments`. Refund amounts may be negative or positive magnitudes; the response normalizes them to negative. Zero bills send `payments: []` and `exchange_mode_of_payment` (for example `CARD`) identifying the configured tender account for the offset. Exchanges currently require full settlement: no residual credit balance. Gift voucher issuance/redemption and explicit header `taxes[]` are unsupported in exchange payloads; send VAT per item. If `rounded_total` is provided, it must equal the signed item total.

ERP receives a sale POS Invoice, one return POS Invoice per original sale, and a standalone return POS Invoice for any items without an original reference. Each posts immediately to its own Sales Invoice/credit note and stock/GL entries. Gross tenders offset through the same payment account; their net is exactly the actual collection/refund. These component tenders must not be treated as separate customer collections. The primary component uses the receipt external reference; auxiliary returns receive deterministic internal references. Components share the customer's bill number. The immutable sync operation retains the complete original receipt.

The response retains `invoice_name`, `pos_invoice_name`, `doctype`, and `docstatus`, and adds `is_exchange: true`, `sale_invoice`, `return_invoices`, `accounting_invoices`, and signed `net_payments`. Response `grand_total` is the **net receipt total**, which differs from the primary component invoice total. Use the component arrays to display every ERP document. For return-only receipts, `sale_invoice` is null and the primary invoice is a return.

All components, stock/accounting effects and the success receipt commit together. Identical retries return the stored result with `duplicate: true`; changed retries fail. A failure rolls back the whole exchange. Do not call the return API separately for negative lines already included in this receipt. A previously synced receipt cannot be converted into an exchange by resending changed data; reconcile it separately.

### Send a completed sale

`POST /api/method/retail.api.pos_sync.create_pos_invoice`

Send the billed prices, VAT, discounts and totals unchanged. Item `discount_amount` is per unit; header `discount_amount` is the bill discount. `amount` is line value before bill discount, excluding VAT; `net_amount` is after all discounts, excluding VAT. ERP permanently accepts the completed sale and posts it when accounting is available. Do not create a second invoice or payment for it.

Keep only actual cash/card tenders in `payments`. Send the unpaid customer portion
in `credit_sale_amount`, and credit-note allocations in `credit_note_redemptions`.
For a fully paid cash/card bill, send `credit_sale_amount: 0` and
`credit_note_redemptions: []`. Credit Sale and Credit Note are not ERP payment modes.
Each redemption row preserves the credit note's permanent POS reference and the
requested amount; multiple rows are supported.

Request JSON:

```json
{
  "external_pos_reference": "KAR-C07-T07-SALE-20260924-000123",
  "external_shift_reference": "KAR-C07-T07-SHIFT-20260924-01",
  "external_session_reference": "KAR-C07-T07-CS-20260924-01",
  "branch": "Karama",
  "counter_code": "C07",
  "pos_terminal_id": "T07",
  "cashier_employee": "E-1",
  "customer": "C-1",
  "posting_date": "2026-09-24",
  "posting_time": "09:15:00",
  "discount_amount": 0,
  "vat_amount": 1,
  "grand_total": 21,
  "items": [
    {
      "item_code": "I-1",
      "qty": 2,
      "rate": 10.5,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 20,
      "net_amount": 20,
      "vat_rate": 5,
      "vat_amount": 1,
      "uom": "Nos",
      "conversion_factor": 1
    }
  ],
  "payments": [
    {
      "mode_of_payment": "Cash",
      "amount": 21
    }
  ],
  "issued_vouchers": [],
  "business_date": "2026-09-24",
  "pos_bill_no": "000123",
  "pos_local_created_at": "2026-09-24 09:15:00",
  "update_stock": 1,
  "credit_sale_amount": 0,
  "credit_note_redemptions": []
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "invoice_name": "POS-1",
    "pos_invoice_name": "POS-1",
    "doctype": "POS Invoice",
    "docstatus": 1,
    "grand_total": 21,
    "outstanding_amount": 0,
    "issued_vouchers": [],
    "rate_audit_rows": [],
    "audit_warnings": [],
    "accepted": true,
    "accepted_transaction": "<Retail acceptance record>",
    "settlement_status": "Reconciled",
    "accounting_outstanding_amount": 0,
    "duplicate": false
  }
}
```

**Same API: sale using credit-note redemption and partial credit**

This complete request records an AED 200 bill: Cash 30, Card 50, Credit Note
Redeemed 100, and Credit Sale 20. Keep the POS-confirmed amounts even when the
referenced credit note has not synced or ERP can currently apply only part of it.
ERP accepts and posts the sale, records unresolved credit separately, and retries
reconciliation internally. No additional API call is needed.

Request JSON:

```json
{
  "external_pos_reference": "SALE-015",
  "external_shift_reference": "KAR-C07-T07-SHIFT-20260924-01",
  "external_session_reference": "KAR-C07-T07-CS-20260924-01",
  "branch": "Karama",
  "counter_code": "C07",
  "pos_terminal_id": "T07",
  "cashier_employee": "E-1",
  "customer": "C-1",
  "posting_date": "2026-09-24",
  "posting_time": "09:15:00",
  "discount_amount": 0,
  "vat_amount": 9.52,
  "grand_total": 200,
  "items": [
    {
      "item_code": "I-1",
      "qty": 2,
      "rate": 100,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 190.48,
      "net_amount": 190.48,
      "vat_rate": 5,
      "vat_amount": 9.52,
      "uom": "Nos",
      "conversion_factor": 1
    }
  ],
  "payments": [
    {
      "mode_of_payment": "Cash",
      "amount": 30
    },
    {
      "mode_of_payment": "Card",
      "amount": 50
    }
  ],
  "issued_vouchers": [],
  "business_date": "2026-09-24",
  "pos_bill_no": "000015",
  "pos_local_created_at": "2026-09-24 09:15:00",
  "update_stock": 1,
  "credit_sale_amount": 20,
  "credit_note_redemptions": [
    {
      "credit_note_external_reference": "RETURN-009",
      "amount": 100
    }
  ]
}
```

After full reconciliation, native accounting outstanding is AED 20. If ERP can
apply only AED 80 of the requested AED 100 credit, accounting outstanding is AED
40 and credit-note unresolved is AED 20. POS history still records AED 100 redeemed
and AED 20 Credit Sale.

`credit_note_external_reference` must exactly match the issued return's
`external_pos_reference`, including any `RETURN` segment. A sale reference or a
reference with a changed prefix remains pending; ERP does not guess another note.
POS Transaction Log and POS Payment Mode Summary show Credit Sale, Credit Note
Issued, and Credit Note Redeemed separately from cash/card. Redemption requested,
applied, and unresolved amounts are separate columns; unused zero-value payment
rows do not count as paid invoices.


### Send an unpaid credit sale

`POST /api/method/retail.api.pos_sync.create_credit_pos_invoice`

Use this existing API for a sale with no initial cash/card payment. Send the full unpaid amount in `credit_sale_amount`; keep `payments` and `credit_note_redemptions` empty. A later credit-limit or customer-balance change does not reject the completed offline bill.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-CREDIT-20260625-000005",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "pos_bill_no": "000005",
  "cashier": "Cashier Display Name",
  "customer": "C-1",
  "posting_date": "2026-06-25",
  "posting_time": "13:30:00",
  "pos_local_created_at": "2026-06-25 13:30:00",
  "update_stock": 1,
  "discount_amount": 0,
  "vat_amount": 1.0,
  "grand_total": 21.0,
  "items": [
    {
      "item_code": "I-1",
      "barcode": "629000000001",
      "uom": "Nos",
      "conversion_factor": 1,
      "qty": 2,
      "rate": 10.5,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 20,
      "net_amount": 20,
      "vat_rate": 5,
      "vat_amount": 1.0
    }
  ],
  "issued_vouchers": [],
  "due_date": "2026-07-25",
  "payments": [],
  "credit_sale_amount": 21.0,
  "credit_note_redemptions": []
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "invoice_name": "POS-1",
    "pos_invoice_name": "POS-1",
    "doctype": "POS Invoice",
    "docstatus": 1,
    "grand_total": 21.0,
    "outstanding_amount": 21.0,
    "issued_vouchers": [],
    "rate_audit_rows": [],
    "audit_warnings": [],
    "accepted": true,
    "accepted_transaction": "<Retail acceptance record>",
    "settlement_status": "Reconciled",
    "accounting_outstanding_amount": 21.0,
    "duplicate": false
  }
}
```

### Customer deposit

`POST /api/method/retail.api.pos_sync.create_customer_deposit`

Money received before an invoice exists. This is not a sale or an increase in the credit limit.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-DEPOSIT-20260625-000006",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "customer": "C-1",
  "payment_mode": "Cash",
  "amount": 50,
  "reference_no": "CASH-000006",
  "posting_date": "2026-06-25",
  "pos_local_created_at": "2026-06-25 13:35:00"
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "payment_entry": "PE-1",
    "docstatus": 1,
    "customer": "C-1",
    "amount": 50,
    "unallocated_amount": 50
  }
}
```

### Collect one payment for one or more invoices

`POST /api/method/retail.api.pos_sync.pay_customer_invoice`

Send one payment with an `invoices` array. Each row identifies the bill using
`invoice_external_reference`, specifies `invoice_doctype` (`POS Invoice` or
`Sales Invoice`), and sends `allocated_amount`. One row or multiple rows (including
10 bills from earlier days) create one Payment Entry with one allocation per bill.
Use the collecting cashier’s current shift/session and collection business date.

Send `customer` and the total collected `amount` at the header. Allocations must
sum exactly to `amount`; each must be positive, use at most two decimal places,
and not exceed its current outstanding balance. ERP reads invoice totals, paid
amounts, and current balances; do not send these in the request. All invoices
must be submitted sales for this customer and the counter's company. Duplicate
invoices, including POS/Sales references resolving to the same accounting invoice,
are rejected. If any row fails, no payment or partial allocation is posted.

Existing single-invoice requests using header `invoice_name` or
`invoice_external_reference` and optional `invoice_doctype` remain supported with
the existing response. Do not combine those header fields with `invoices`.
Rows may alternatively identify the bill using `invoice_name`. Keep the same
`external_pos_reference` and unchanged request on retries; a successful retry
returns the same payment without collecting again.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-COLLECTION-20260626-000007",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-2",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260626-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260626-000001",
  "business_date": "2026-06-26",
  "customer": "C-1",
  "payment_mode": "Cash",
  "amount": 300,
  "invoices": [
    {
      "invoice_external_reference": "KARAMA-C001-T001-CREDIT-20260625-000005",
      "invoice_doctype": "POS Invoice",
      "allocated_amount": 100
    },
    {
      "invoice_external_reference": "KARAMA-C001-T001-CREDIT-20260624-000004",
      "invoice_doctype": "POS Invoice",
      "allocated_amount": 200
    }
  ],
  "reference_no": "CASH-000007",
  "posting_date": "2026-06-26",
  "pos_local_created_at": "2026-06-26 10:00:00"
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "payment_entry": "PE-2",
    "docstatus": 1,
    "customer": "C-1",
    "amount": 300,
    "allocated_amount": 300,
    "invoices": [
      {
        "invoice_external_reference": "KARAMA-C001-T001-CREDIT-20260625-000005",
        "invoice_name": "POS-1",
        "invoice_doctype": "POS Invoice",
        "sales_invoice": "SI-1",
        "allocated_amount": 100,
        "invoice_outstanding_amount": 0
      },
      {
        "invoice_external_reference": "KARAMA-C001-T001-CREDIT-20260624-000004",
        "invoice_name": "POS-2",
        "invoice_doctype": "POS Invoice",
        "sales_invoice": "SI-2",
        "allocated_amount": 200,
        "invoice_outstanding_amount": 50
      }
    ],
    "duplicate": false
  }
}
```

### Return a paid sale

`POST /api/method/retail.api.pos_sync.create_pos_return_invoice`

Send positive quantities and refund amounts; ERP creates the negative return. If the original bill is known, send `original_external_pos_reference` (or `original_pos_invoice`). The return can arrive first: ERP accepts it and posts it automatically after the original arrives. If neither original reference is supplied, ERP creates a standalone return with no original invoice link and uses its unlinked return valuation rules.

Choose one `return_settlement_type` in this same request:

| Value | Meaning | `payments` |
| --- | --- | --- |
| `Cash Refund` | Refund cash | Full refund amount in Cash rows |
| `Card Refund` | Refund to card | Full refund amount in Card rows |
| `Reusable Customer Credit` | Issue a credit note for later bills | `[]` |
| `Original Debt Reduction` | Reduce the original unpaid bill only | `[]` |

The same return cannot both reduce the original debt and create reusable credit.
Each return keeps its own permanent `external_pos_reference`.

Request JSON:


```json
{
  "external_pos_reference": "KARAMA-C001-T001-R-20260625-000003",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "pos_bill_no": "000003",
  "cashier": "Cashier Display Name",
  "customer": "C-1",
  "posting_date": "2026-06-25",
  "posting_time": "13:40:00",
  "pos_local_created_at": "2026-06-25 13:40:00",
  "update_stock": 1,
  "discount_amount": 0,
  "vat_amount": 0.5,
  "grand_total": 10.5,
  "items": [
    {
      "item_code": "I-1",
      "barcode": "629000000001",
      "uom": "Nos",
      "conversion_factor": 1,
      "qty": 1,
      "rate": 10.5,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 10,
      "net_amount": 10,
      "vat_rate": 5,
      "vat_amount": 0.5
    }
  ],
  "payments": [
    {
      "mode_of_payment": "Cash",
      "amount": 10.5,
      "reference_no": "CASH-000003"
    }
  ],
  "original_external_pos_reference": "KARAMA-C001-T001-S-20260625-000002",
  "return_settlement_type": "Cash Refund"
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "return_invoice": "POS-2",
    "doctype": "POS Invoice",
    "docstatus": 1,
    "grand_total": -10.5,
    "outstanding_amount": 0,
    "rate_audit_rows": [],
    "accepted": true,
    "accepted_transaction": "<Retail acceptance record>",
    "settlement_status": "Reconciled",
    "accounting_outstanding_amount": 0,
    "duplicate": false
  }
}
```

**Same API: issue a reusable credit note**

Use this complete return payload to issue AED 100 reusable credit. `RETURN-009`
is the reference a later sale sends in `credit_note_redemptions`; keep it separate
from the original sale reference `SALE-001`. If the original sale has not arrived,
ERP accepts this return and posts it automatically after the original arrives.

Request JSON:

```json
{
  "external_pos_reference": "RETURN-009",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "pos_bill_no": "000009",
  "cashier": "Cashier Display Name",
  "customer": "C-1",
  "posting_date": "2026-06-25",
  "posting_time": "13:40:00",
  "pos_local_created_at": "2026-06-25 13:40:00",
  "update_stock": 1,
  "discount_amount": 0,
  "vat_amount": 4.76,
  "grand_total": 100,
  "items": [
    {
      "item_code": "I-1",
      "barcode": "629000000001",
      "uom": "Nos",
      "conversion_factor": 1,
      "qty": 1,
      "rate": 100,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 95.24,
      "net_amount": 95.24,
      "vat_rate": 5,
      "vat_amount": 4.76
    }
  ],
  "payments": [],
  "original_external_pos_reference": "SALE-001",
  "return_settlement_type": "Reusable Customer Credit"
}
```

For a card refund, use `return_settlement_type: "Card Refund"` and actual Card
payment rows for the full refund amount instead of this reusable-credit settlement.


### Return an unpaid credit sale

`POST /api/method/retail.api.pos_sync.create_pos_return_invoice`

Send positive returned quantities and amounts, `return_settlement_type: "Original Debt Reduction"`, and `payments: []`. ERP allocates the return only against the original unpaid bill; it does not also create reusable credit. The original sale may arrive later: ERP accepts the return now and resolves its dependency internally.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-CREDITRETURN-20260625-000012",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "pos_bill_no": "000012",
  "cashier": "Cashier Display Name",
  "customer": "C-1",
  "posting_date": "2026-06-25",
  "posting_time": "13:40:00",
  "pos_local_created_at": "2026-06-25 13:40:00",
  "update_stock": 1,
  "discount_amount": 0,
  "vat_amount": 0.5,
  "grand_total": 10.5,
  "items": [
    {
      "item_code": "I-1",
      "barcode": "629000000001",
      "uom": "Nos",
      "conversion_factor": 1,
      "qty": 1,
      "rate": 10.5,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 10,
      "net_amount": 10,
      "vat_rate": 5,
      "vat_amount": 0.5
    }
  ],
  "original_external_pos_reference": "KARAMA-C001-T001-CREDIT-20260625-000005",
  "return_settlement_type": "Original Debt Reduction",
  "payments": []
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "return_invoice": "POS-2",
    "doctype": "POS Invoice",
    "docstatus": 1,
    "grand_total": -10.5,
    "outstanding_amount": -10.5,
    "rate_audit_rows": [],
    "accepted": true,
    "accepted_transaction": "<Retail acceptance record>",
    "settlement_status": "Reconciled",
    "accounting_outstanding_amount": 0,
    "duplicate": false
  }
}
```

### Separate payment for a Sales Invoice

`POST /api/method/retail.api.pos_sync.create_pos_payment_entry`

For existing Sales Invoices. Do not repeat a payment already included in a POS sale.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-PAY-20260625-000004",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260625-000001",
  "business_date": "2026-06-25",
  "sales_invoice": "SI-1",
  "mode_of_payment": "Cash",
  "paid_amount": 21,
  "reference_no": "CASH-000004",
  "posting_date": "2026-06-25"
}
```

Response example:

```json
{"message": {"status": "Success", "payment_entry": "PE-3", "docstatus": 1}}
```

## Customers and stock

### Create or update customer

`POST /api/method/retail.api.pos_sync.upsert_customer`

Save the returned customer ID before using it on a bill. Existing customers return `action: "Updated"`. Empty text clears a field; omitted fields stay unchanged.

Request JSON:

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

Response example:

```json
{"message": {"status": "Success", "action": "Created", "customer": "C-1"}}
```

### Customer balances and unused credit notes

`GET /api/method/retail.api.pos_sync.get_customer_balances?company=nesto&from_date=2026-01-01&to_date=2026-07-22&include_zero_balance=1`

Optional: `customer=C-1` for one customer. Refresh before checkout. Credit-note values are current, even with an older `to_date`. They are already included in the net balance; do not subtract them again. This call does not spend or reserve credit.

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "status": "Success",
    "company": "nesto",
    "from_date": "2026-01-01",
    "to_date": "2026-07-22",
    "count": 1,
    "data": [
      {
        "customer": "C-1",
        "customer_name": "Customer Name",
        "email": "customer@example.com",
        "phone": "9715XXXXXXXX",
        "opening_balance": 1000.0,
        "transaction_amount": 500.0,
        "payment_amount": 300.0,
        "current_balance": 1200.0,
        "address": "Dubai, UAE",
        "address_id": "Customer Name-Billing",
        "unused_credit_note_amount": 100.0,
        "credit_note_currency": "AED",
        "credit_notes_as_of": "2026-09-28 12:00:00",
        "unused_credit_notes": [
          {
            "reference_doctype": "Sales Invoice",
            "reference_name": "SI-RETURN-001",
            "receivable_account": "Debtors - N",
            "remaining_amount": 100.0,
            "currency": "AED",
            "remaining_amount_in_account_currency": 100.0,
            "account_currency": "AED"
          }
        ]
      }
    ]
  }
}
```

### Refresh stock

`POST /api/method/retail.api.pos_sync.get_warehouse_stock_snapshot`

Request JSON:

```json
{"branch": "Karama", "counter_code": "C001", "item_codes": ["I-1"]}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "warehouse": "Stores - N",
    "generated_at": "2026-09-30 09:00:00",
    "stock": [
      {
        "item_code": "I-1",
        "actual_qty": 100,
        "current_stock": 100,
        "reserved_qty": 0,
        "projected_qty": 100,
        "stock_value": 500,
        "modified": "2026-09-30 09:00:00",
        "modified_on": "2026-09-30 09:00:00"
      }
    ]
  }
}
```

## Promotions, loyalty and gift vouchers

### Download special prices

`GET /api/method/retail.api.pos_sync.get_pos_promo_prices?branch=Karama&counter_code=C001`

Optional `modified_after`. Keep a separate saved time for each API. Apply the returned dates, scope and disabled flags; do not recalculate saved bills.

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "status": "Success",
    "server_time": "2026-09-30 09:00:00",
    "branch": "Karama",
    "counter": "Karama-C001",
    "counter_code": "C001",
    "promotions": []
  }
}
```

### Download buy/get offers

`GET /api/method/retail.api.pos_sync.get_pos_buy_x_get_y_promotions?branch=Karama&counter_code=C001`

Optional `modified_after`. Keep a separate saved time for each API. Apply the returned dates, scope and disabled flags; do not recalculate saved bills.

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "status": "Success",
    "server_time": "2026-09-30 09:00:00",
    "branch": "Karama",
    "counter": "Karama-C001",
    "counter_code": "C001",
    "promotions": []
  }
}
```

### Download loyalty programs

`GET /api/method/retail.api.pos_sync.get_pos_loyalty_programs?branch=Karama&counter_code=C001`

Optional `modified_after`. Keep a separate saved time for each API. Apply the returned dates, scope and disabled flags; do not recalculate saved bills.

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "status": "Success",
    "server_time": "2026-09-30 09:00:00",
    "branch": "Karama",
    "counter": "Karama-C001",
    "counter_code": "C001",
    "loyalty_programs": []
  }
}
```

### Issue a gift voucher with a sale

`POST /api/method/retail.api.pos_sync.create_pos_invoice`

Generate `PGV-` plus 32 uppercase hexadecimal characters. The voucher can be spent after this sale syncs. Response shown with selected voucher fields.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-SALE-20260924-000123",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260924-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260924-000001",
  "business_date": "2026-09-24",
  "pos_bill_no": "000123",
  "cashier": "Cashier Display Name",
  "customer": "C-1",
  "posting_date": "2026-09-24",
  "posting_time": "09:15:00",
  "pos_local_created_at": "2026-09-24 09:15:00",
  "update_stock": 1,
  "discount_amount": 0,
  "vat_amount": 1.0,
  "grand_total": 21.0,
  "items": [
    {
      "item_code": "I-1",
      "barcode": "629000000001",
      "uom": "Nos",
      "conversion_factor": 1,
      "qty": 2,
      "rate": 10.5,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 20,
      "net_amount": 20,
      "vat_rate": 5,
      "vat_amount": 1.0
    }
  ],
  "payments": [{"mode_of_payment": "Cash", "amount": 21.0, "reference_no": "CASH-000123"}],
  "issued_vouchers": [
    {
      "voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF",
      "voucher_amount": 10,
      "issued_date": "2026-09-24",
      "expiry_date": "2026-10-24",
      "promotion": "September Gift Voucher Promotion",
      "customer": "C-1"
    }
  ]
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "invoice_name": "POS-1",
    "pos_invoice_name": "POS-1",
    "doctype": "POS Invoice",
    "docstatus": 1,
    "grand_total": 21,
    "outstanding_amount": 0,
    "issued_vouchers": [{"voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF", "voucher_amount": 10}],
    "rate_audit_rows": [],
    "audit_warnings": []
  }
}
```

### Find gift voucher

`POST /api/method/retail.api.gift_vouchers.get_gift_voucher`

Missing voucher: `found: false, valid: false, reason: "Not registered"`.

Request JSON:

```json
{"branch": "Karama", "counter_code": "C001", "voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF"}
```

Response example:

```json
{
  "message": {
    "found": true,
    "valid": true,
    "reason": null,
    "voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF",
    "voucher_amount": 10,
    "balance_amount": 10,
    "status": "Unused",
    "expiry_date": "2026-10-24",
    "company": "nesto",
    "currency": "AED",
    "server_date": "2026-09-30"
  }
}
```

### Approve voucher spending

`POST /api/method/retail.api.gift_vouchers.redeem_gift_voucher`

Online only. Wait for `approved: true` before completing the purchase. Retry the same `redemption_reference` after a timeout.

Request JSON:

```json
{
  "branch": "Karama",
  "counter_code": "C001",
  "voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF",
  "amount": 10.0,
  "external_pos_reference": "KARAMA-C001-T001-SALE-20260924-000124",
  "redemption_reference": "KARAMA-C001-T001-REDEEM-20260924-000124"
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "approved": true,
    "voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF",
    "amount": 10.0,
    "balance_after": 0.0,
    "redemption_reference": "KARAMA-C001-T001-REDEEM-20260924-000124",
    "duplicate": false
  }
}
```

### Send sale using an approved voucher

`POST /api/method/retail.api.pos_sync.create_pos_invoice`

Use the approved voucher, amount and sale reference. Include its benefit in discounts/totals; send only remaining cash/card payments.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-C001-T001-SALE-20260924-000124",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260924-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20260924-000001",
  "business_date": "2026-09-24",
  "pos_bill_no": "000124",
  "cashier": "Cashier Display Name",
  "customer": "C-1",
  "posting_date": "2026-09-24",
  "posting_time": "09:30:00",
  "pos_local_created_at": "2026-09-24 09:30:00",
  "update_stock": 1,
  "discount_amount": 9.52,
  "vat_amount": 0.52,
  "grand_total": 11,
  "items": [
    {
      "item_code": "I-1",
      "barcode": "629000000001",
      "uom": "Nos",
      "conversion_factor": 1,
      "qty": 2,
      "rate": 10.5,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 20,
      "net_amount": 10.48,
      "vat_rate": 5,
      "vat_amount": 0.52
    }
  ],
  "payments": [{"mode_of_payment": "Cash", "amount": 11, "reference_no": "CASH-000124"}],
  "issued_vouchers": [],
  "voucher_redemption": {
    "voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF",
    "amount": 10,
    "redemption_reference": "KARAMA-C001-T001-REDEEM-20260924-000124"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "invoice_name": "POS-1",
    "pos_invoice_name": "POS-1",
    "doctype": "POS Invoice",
    "docstatus": 1,
    "grand_total": 11,
    "outstanding_amount": 0,
    "issued_vouchers": [],
    "rate_audit_rows": [],
    "audit_warnings": []
  }
}
```

### Undo voucher approval for an abandoned purchase

`POST /api/method/retail.api.gift_vouchers.reverse_gift_voucher_redemption`

Only before the approval is linked to an invoice. Keep local cashier/session records for voucher approvals and reversals.

`customer` is optional and may be sent as the ERP customer ID. The API ignores
this field: reversal uses `redemption_reference` and validates the original
approval's company and counter. It does not assign credit to a customer.

Request JSON:

```json
{
  "branch": "Karama",
  "counter_code": "C001",
  "customer": "C-1",
  "redemption_reference": "KARAMA-C001-T001-REDEEM-20260924-000124"
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "redemption_reference": "KARAMA-C001-T001-REDEEM-20260924-000124",
    "voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF",
    "amount": 10,
    "balance_after": 10,
    "duplicate": false
  }
}
```

### Download gift voucher offers

`POST /api/method/retail.api.gift_vouchers.get_gift_voucher_promotions`

Also included in master data. Use a full download; `server_date` is not a changes-since timestamp.

Request JSON:

```json
{"branch": "Karama", "counter_code": "C001"}
```

Response example:

```json
{"message": {"promotions": [], "server_date": "2026-09-30"}}
```

## Sync checks

### Check saved request status

`POST /api/method/retail.api.pos_sync.get_sync_status`

Use the saved `response` to recover IDs. `Not Found` means retry the original request, with the original reference.

Request JSON:

```json
{"external_references": ["KAR-C07-T07-SHIFTOPEN-20260924-01"]}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "references": {
      "KAR-C07-T07-SHIFTOPEN-20260924-01": {
        "status": "Synced",
        "pos_invoice": null,
        "payment_entry": null,
        "latest_log": null,
        "response": {
          "status": "Success",
          "cashier_shift": "PSH-1",
          "counter_session": "PCS-1",
          "pos_opening_entry": "POE-1"
        }
      }
    }
  }
}
```

### Check whether the original sale has arrived

`POST /api/method/retail.api.pos_sync.get_queue_dependencies`

This checks sale/return references only. POS must also wait for shift, session and payment dependencies.

Request JSON:

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

Response example:

```json
{
  "message": {
    "status": "Success",
    "dependencies": {
      "KARAMA-C001-T001-R-20260625-000003": {"already_synced": false, "original_invoice_synced": true, "can_sync": true}
    }
  }
}
```

### Save queue errors in ERP

`POST /api/method/retail.api.pos_sync.ingest_queue_errors`

This saves the error report; it does not complete the failed action. The example below describes a historical client queue error. Missing original-sale dependencies no longer block acceptance of completed returns.

Request JSON:

```json
{
  "branch": "Karama",
  "counter_code": "C001",
  "errors": [
    {
      "external_pos_reference": "KARAMA-C001-T001-R-20260625-000003",
      "status": "BlockedDependency",
      "error": "Original sale is still pending"
    }
  ]
}
```

Response example:

```json
{"message": {"status": "Success", "logs": ["PSL-1"]}}
```

## Day closing and manager corrections

Stop billing and finish sending all counters’ queues before closing. For a closed day: reopen, send missing bills or corrections, then use the same submit API again. Missing completed bills keep their original date, references and shift/session, even when the historical shift is closed.

Corrections require the manager’s own login/token, an active branch Employee with POS Login Enabled, POS access and record access. Shared integration credentials cannot approve corrections.

| Action | Required permission |
|---|---|
| Reopen day | `REOPEN_DAY_CLOSING` |
| Correct counted cash | `ADJUST_DAY_CLOSING_PAYMENTS` |
| Change initial Cash/Card payment | `CHANGE_SETTLED_BILL_MOP` |
| Credit and collection corrections | `CHANGE_BILL_SETTLEMENT` |
| Recalculate or close reopened day | `DAY_CLOSING` |

### Prepare day closing

`POST /api/method/retail.api.pos_sync.make_branch_day_closing`

Creates or returns the current closing. Response is the closing document; selected fields shown.

Request JSON:

```json
{"branch": "Karama", "business_date": "2026-09-30"}
```

Response example:

```json
{
  "message": {
    "name": "PDC-1",
    "doctype": "POS Branch Day Closing",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "docstatus": 0
  }
}
```

### Close or reclose the day

`POST /api/method/retail.api.pos_sync.submit_branch_day_closing`

No reason is needed. Recalculates totals and closes in one call. Use a new close reference after each reopening; retry a timeout with the same reference. Collections are included in payment totals, not sales totals.

Request JSON:

```json
{
  "data": {
    "branch": "Karama",
    "business_date": "2026-09-30",
    "external_pos_reference": "KARAMA-DAYCLOSE-20260930-000002"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Closed",
    "docstatus": 1,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {"Cash": 21},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 121,
    "counted_cash": 121,
    "variance": 0,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false,
    "name": "PDC-2"
  }
}
```

### Reopen a closed day

`POST /api/method/retail.pos_day_corrections.reopen_day_closing`

Use the returned `day_closing` ID for the following corrections. Each new correction needs a fresh reference; timeout retries keep the same body, reference and manager login.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-1",
    "operation_reference": "DAY-REOPEN-001",
    "reason": "Manager checked the correction"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Reopened",
    "docstatus": 0,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {"Cash": 21},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 121,
    "counted_cash": 121,
    "variance": 0,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false
  }
}
```

### Read bill payment rows

`GET /api/method/retail.pos_day_corrections.get_bill_payment_details?day_closing=PDC-2&pos_invoice=POS-1`

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "day_closing": "PDC-2",
    "pos_invoice": "POS-1",
    "payment_revision": 0,
    "payments": [
      {
        "payment_row": "<payment row ID>",
        "mode_of_payment": "Cash",
        "account": "<Cash account ID>",
        "amount": 21
      }
    ]
  }
}
```

### Change a bill from Cash to Card

`POST /api/method/retail.pos_day_corrections.correct_settled_bill_mop`

Read payment details first. Send every nonzero payment row once, including unchanged split rows. Send row ID and payment method only; amounts cannot change. Do not resend the original bill with changed payments.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-2",
    "operation_reference": "BILL-MOP-001",
    "reason": "Manager checked the correction",
    "pos_invoice": "POS-1",
    "expected_payment_revision": 0,
    "payments": [{"payment_row": "<payment row ID>", "mode_of_payment": "Card"}]
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Reopened",
    "docstatus": 0,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {"Card": 21},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 100,
    "counted_cash": 121,
    "variance": 21,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false,
    "invoice_name": "POS-1",
    "accounting_invoice": "SI-1",
    "payment_revision": 1,
    "accounting_repost": "<repost ID>",
    "before_payments": [
      {
        "payment_row": "<payment row ID>",
        "mode_of_payment": "Cash",
        "account": "<Cash account ID>",
        "amount": 21
      }
    ],
    "payments": [
      {
        "payment_row": "<payment row ID>",
        "mode_of_payment": "Card",
        "account": "<Card account ID>",
        "amount": 21
      }
    ]
  }
}
```

### Correct counted cash

`POST /api/method/retail.pos_day_corrections.adjust_day_closing_payments`

`expected_amount` is the currently saved counted cash, not the amount calculated from sales. Use a closed shift from this day.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-2",
    "operation_reference": "COUNT-001",
    "reason": "Manager checked the correction",
    "counted_cash": [{"cashier_shift": "PSH-1", "expected_amount": 121, "closing_amount": 120}]
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Reopened",
    "docstatus": 0,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {"Cash": 21},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 121,
    "counted_cash": 120,
    "variance": -1,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false,
    "counted_cash_changes": [{"cashier_shift": "PSH-1", "before": 121, "after": 120}]
  }
}
```

### Preview day totals (optional)

`POST /api/method/retail.pos_day_corrections.recalculate_day_closing`

No reason is needed.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-2",
    "operation_reference": "DAY-PREVIEW-001"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Reopened",
    "docstatus": 0,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {"Cash": 21},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 121,
    "counted_cash": 121,
    "variance": 0,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false
  }
}
```

### Close using reviewed totals (optional)

`POST /api/method/retail.pos_day_corrections.reclose_day_closing`

The normal submit API above is enough. Use this only when the manager must approve the exact preview totals.

No reason is needed.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-2",
    "operation_reference": "DAY-REVIEW-CLOSE-001",
    "expected_reconciliation_hash": "<hash from preview>"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Closed",
    "docstatus": 1,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {"Cash": 21},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 121,
    "counted_cash": 121,
    "variance": 0,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false
  }
}
```

### Check available day buttons

`GET /api/method/retail.pos_day_corrections.get_day_correction_actions?day_closing=PDC-2`

Request body: none; use the URL values above.

Response example:

```json
{"message": {"reopen": false, "recalculate": true, "reclose": true}}
```

## Credit and collection corrections

Use the sale day to remove its original payment. Use the collection day to record, amend or reverse a collection. Reopen that day if closed; otherwise prepare its draft closing. A later collection does not require reopening the old sale day.

Read details first and copy the latest `settlement_hash` into `expected_settlement_hash`. If the bill changes, refresh and confirm again using a new operation reference. Customer, items and prices stay the same.

### Read settlement details

`GET /api/method/retail.pos_settlement_corrections.get_settlement_details?day_closing=PDC-2&pos_invoice=POS-1`

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "day_closing": "PDC-2",
    "pos_invoice": "POS-1",
    "accounting_invoice": "SI-1",
    "customer": "C-1",
    "payment_revision": 0,
    "initial_paid_amount": 21,
    "outstanding_amount": 0,
    "payments": [
      {
        "payment_row": "<payment row ID>",
        "mode_of_payment": "Cash",
        "account": "<Cash account ID>",
        "amount": 21
      }
    ],
    "collections": [],
    "settlement_hash": "<latest hash>"
  }
}
```

### Change a paid bill to credit

`POST /api/method/retail.pos_settlement_corrections.correct_bill_settlement`

Only a fully paid bill with no later collections. The same customer must qualify for credit. This corrects money recorded by mistake; it does not refund cash or a card.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-2",
    "operation_reference": "SETTLEMENT-SetCredit-001",
    "reason": "Manager checked the correction",
    "pos_invoice": "POS-1",
    "action": "SetCredit",
    "expected_settlement_hash": "<latest hash from details>"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Reopened",
    "docstatus": 0,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 100,
    "counted_cash": 121,
    "variance": 21,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false,
    "action": "SetCredit",
    "invoice_name": "POS-1",
    "before_settlement": {
      "pos_invoice": "POS-1",
      "accounting_invoice": "SI-1",
      "customer": "C-1",
      "payment_revision": 0,
      "initial_paid_amount": 21,
      "outstanding_amount": 0,
      "payments": [
        {
          "payment_row": "<payment row ID>",
          "mode_of_payment": "Cash",
          "account": "<Cash account ID>",
          "amount": 21
        }
      ],
      "collections": [],
      "settlement_hash": "<latest hash>"
    },
    "settlement": {
      "pos_invoice": "POS-1",
      "accounting_invoice": "SI-1",
      "customer": "C-1",
      "payment_revision": 1,
      "initial_paid_amount": 0,
      "outstanding_amount": 21,
      "payments": [],
      "collections": [],
      "settlement_hash": "<new hash>"
    },
    "accounting_repost": "<repost ID>"
  }
}
```

### Record a missing credit collection

`POST /api/method/retail.pos_settlement_corrections.correct_bill_settlement`

Partial or full payment, up to the outstanding balance. Use the collection day’s shift/session. Optional `reference_no`.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-2",
    "operation_reference": "SETTLEMENT-CollectCredit-001",
    "reason": "Manager checked the correction",
    "pos_invoice": "POS-1",
    "action": "CollectCredit",
    "expected_settlement_hash": "<latest hash from details>",
    "amount": 21,
    "mode_of_payment": "Cash",
    "reference_no": "CASH-001",
    "cashier_shift": "PSH-1",
    "counter_session": "PCS-1"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Reopened",
    "docstatus": 0,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {"Cash": 21},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 121,
    "counted_cash": 121,
    "variance": 0,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false,
    "action": "CollectCredit",
    "invoice_name": "POS-1",
    "before_settlement": {
      "pos_invoice": "POS-1",
      "accounting_invoice": "SI-1",
      "customer": "C-1",
      "payment_revision": 1,
      "initial_paid_amount": 0,
      "outstanding_amount": 21,
      "payments": [],
      "collections": [],
      "settlement_hash": "<new hash>"
    },
    "settlement": {
      "pos_invoice": "POS-1",
      "accounting_invoice": "SI-1",
      "customer": "C-1",
      "payment_revision": 2,
      "initial_paid_amount": 0,
      "outstanding_amount": 0,
      "payments": [],
      "collections": [
        {
          "payment_entry": "PE-4",
          "modified": "2026-09-30 12:00:00",
          "posting_date": "2026-09-30",
          "mode_of_payment": "Cash",
          "amount": 21,
          "account": "<Cash account ID>",
          "cashier_shift": "PSH-1",
          "counter_session": "PCS-1",
          "references": [{"doctype": "Sales Invoice", "name": "SI-1", "amount": 21}]
        }
      ],
      "settlement_hash": "<new hash>"
    },
    "payment_entry": "PE-4"
  }
}
```

### Change a collection from Cash to Card

`POST /api/method/retail.pos_settlement_corrections.correct_bill_settlement`

Save the replacement Payment Entry ID. The amount stays the same.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-2",
    "operation_reference": "SETTLEMENT-ChangeCollectionMOP-001",
    "reason": "Manager checked the correction",
    "pos_invoice": "POS-1",
    "action": "ChangeCollectionMOP",
    "expected_settlement_hash": "<latest hash from details>",
    "payment_entry": "PE-4",
    "mode_of_payment": "Card",
    "reference_no": "CARD-001"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Reopened",
    "docstatus": 0,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {"Card": 21},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 100,
    "counted_cash": 121,
    "variance": 21,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false,
    "action": "ChangeCollectionMOP",
    "invoice_name": "POS-1",
    "before_settlement": {
      "pos_invoice": "POS-1",
      "accounting_invoice": "SI-1",
      "customer": "C-1",
      "payment_revision": 2,
      "initial_paid_amount": 0,
      "outstanding_amount": 0,
      "payments": [],
      "collections": [
        {
          "payment_entry": "PE-4",
          "modified": "2026-09-30 12:00:00",
          "posting_date": "2026-09-30",
          "mode_of_payment": "Cash",
          "amount": 21,
          "account": "<Cash account ID>",
          "cashier_shift": "PSH-1",
          "counter_session": "PCS-1",
          "references": [{"doctype": "Sales Invoice", "name": "SI-1", "amount": 21}]
        }
      ],
      "settlement_hash": "<new hash>"
    },
    "settlement": {
      "pos_invoice": "POS-1",
      "accounting_invoice": "SI-1",
      "customer": "C-1",
      "payment_revision": 3,
      "initial_paid_amount": 0,
      "outstanding_amount": 0,
      "payments": [],
      "collections": [
        {
          "payment_entry": "PE-5",
          "modified": "2026-09-30 12:00:00",
          "posting_date": "2026-09-30",
          "mode_of_payment": "Card",
          "amount": 21,
          "account": "<Card account ID>",
          "cashier_shift": "PSH-1",
          "counter_session": "PCS-1",
          "references": [{"doctype": "Sales Invoice", "name": "SI-1", "amount": 21}]
        }
      ],
      "settlement_hash": "<new hash>"
    },
    "cancelled_payment_entry": "PE-4",
    "payment_entry": "PE-5"
  }
}
```

### Undo a collection recorded by mistake

`POST /api/method/retail.pos_settlement_corrections.correct_bill_settlement`

The customer owes this amount again and must qualify for credit. This does not physically refund money.

Request JSON:

```json
{
  "data": {
    "day_closing": "PDC-2",
    "operation_reference": "SETTLEMENT-ReverseCollection-001",
    "reason": "Manager checked the correction",
    "pos_invoice": "POS-1",
    "action": "ReverseCollection",
    "expected_settlement_hash": "<latest hash from details>",
    "payment_entry": "PE-4"
  }
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "day_closing": "PDC-2",
    "previous_closing": "PDC-1",
    "branch": "Karama",
    "business_date": "2026-09-30",
    "revision": 1,
    "state": "Reopened",
    "docstatus": 0,
    "reconciliation_hash": "<returned hash>",
    "payment_totals": {},
    "total_sales": 21,
    "invoice_count": 1,
    "expected_cash": 100,
    "counted_cash": 121,
    "variance": 21,
    "open_shifts": 0,
    "active_sessions": 0,
    "duplicate": false,
    "action": "ReverseCollection",
    "invoice_name": "POS-1",
    "before_settlement": {
      "pos_invoice": "POS-1",
      "accounting_invoice": "SI-1",
      "customer": "C-1",
      "payment_revision": 2,
      "initial_paid_amount": 0,
      "outstanding_amount": 0,
      "payments": [],
      "collections": [
        {
          "payment_entry": "PE-4",
          "modified": "2026-09-30 12:00:00",
          "posting_date": "2026-09-30",
          "mode_of_payment": "Cash",
          "amount": 21,
          "account": "<Cash account ID>",
          "cashier_shift": "PSH-1",
          "counter_session": "PCS-1",
          "references": [{"doctype": "Sales Invoice", "name": "SI-1", "amount": 21}]
        }
      ],
      "settlement_hash": "<new hash>"
    },
    "settlement": {
      "pos_invoice": "POS-1",
      "accounting_invoice": "SI-1",
      "customer": "C-1",
      "payment_revision": 3,
      "initial_paid_amount": 0,
      "outstanding_amount": 21,
      "payments": [],
      "collections": [],
      "settlement_hash": "<new hash>"
    },
    "cancelled_payment_entry": "PE-4"
  }
}
```

Locked accounting dates, bank-cleared payments, returns, combined invoices, foreign-currency payments, change given, write-offs, loyalty/voucher settlements and unsupported allocations may need accounts-team review. Show the server’s reason.

## Older APIs — existing clients only

Use the cashier-shift and manager day-correction APIs above for new screens.

### Old day cancellation

`POST /api/method/retail.api.pos_sync.cancel_branch_day_closing`

Reason is required. Response is the cancelled document; selected fields shown.

Request JSON:

```json
{"branch": "Karama", "business_date": "2026-06-25", "cancel_reason": "Cash count correction required"}
```

Response example:

```json
{
  "message": {
    "name": "PDC-1",
    "doctype": "POS Branch Day Closing",
    "branch": "Karama",
    "business_date": "2026-06-25",
    "docstatus": 2
  }
}
```

### Reopen a closed cashier shift

`POST /api/method/retail.api.pos_sync.reopen_cashier_shift`

The day must be open first. Close the shift again before closing the day.

Request JSON:

```json
{
  "external_pos_reference": "KARAMA-REOPEN-20260625-000001",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20260625-000001",
  "branch": "Karama",
  "business_date": "2026-06-25",
  "reopen_reason": "Wrong closing cash entered"
}
```

Response example:

```json
{"message": {"status": "Success", "cashier_shift": "PSH-1", "shift_status": "Paused"}}
```

### Old counter opening

`POST /api/method/retail.api.pos_sync.open_pos_shift`

Request JSON:

```json
{
  "external_pos_reference": "LEGACY-OPEN-001",
  "branch": "Karama",
  "counter_code": "C001",
  "business_date": "2026-09-30",
  "posting_date": "2026-09-30",
  "opened_at": "2026-09-30 09:00:00",
  "opening_balances": [{"mode_of_payment": "Cash", "opening_amount": 100}]
}
```

Response example:

```json
{"message": {"status": "Success", "pos_opening_entry": "POE-1", "opened_at": "2026-09-30 09:00:00"}}
```

### Old counter closing

`POST /api/method/retail.api.pos_sync.close_pos_shift`

Request JSON:

```json
{
  "external_pos_reference": "LEGACY-CLOSE-001",
  "branch": "Karama",
  "counter_code": "C001",
  "business_date": "2026-09-30",
  "pos_opening_entry": "POE-1",
  "closing_balances": [{"mode_of_payment": "Cash", "closing_amount": 121}]
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "pos_closing_entry": "PCE-1",
    "pos_opening_entry": "POE-1",
    "closing_status": "Submitted"
  }
}
```

### Old sale name

`POST /api/method/retail.api.pos_sync.create_pos_sales_invoice`

Alias of `create_pos_invoice`. Use the current name for new development.

Request JSON:

```json
{
  "external_pos_reference": "KAR-C07-T07-SALE-20260924-000123",
  "external_shift_reference": "KAR-C07-T07-SHIFT-20260924-01",
  "external_session_reference": "KAR-C07-T07-CS-20260924-01",
  "branch": "Karama",
  "counter_code": "C07",
  "pos_terminal_id": "T07",
  "cashier_employee": "E-1",
  "customer": "C-1",
  "posting_date": "2026-09-24",
  "posting_time": "09:15:00",
  "discount_amount": 0,
  "vat_amount": 1,
  "grand_total": 21,
  "items": [
    {
      "item_code": "I-1",
      "qty": 2,
      "rate": 10.5,
      "rate_includes_vat": 1,
      "discount_amount": 0,
      "amount": 20,
      "net_amount": 20,
      "vat_rate": 5,
      "vat_amount": 1,
      "uom": "Nos",
      "conversion_factor": 1
    }
  ],
  "payments": [{"mode_of_payment": "Cash", "amount": 21}],
  "issued_vouchers": [],
  "business_date": "2026-09-24",
  "pos_bill_no": "000123",
  "pos_local_created_at": "2026-09-24 09:15:00",
  "update_stock": 1
}
```

Response example:

```json
{
  "message": {
    "status": "Success",
    "invoice_name": "POS-1",
    "pos_invoice_name": "POS-1",
    "doctype": "POS Invoice",
    "docstatus": 1,
    "grand_total": 21,
    "outstanding_amount": 0,
    "issued_vouchers": [],
    "rate_audit_rows": [],
    "audit_warnings": []
  }
}
```

## Failed requests

Example for lifecycle actions or collections: opening has not arrived yet. Send it first, then retry the unchanged request. Completed sales/returns/exchanges are accepted instead; see the settlement section below.

```json
{
  "message": {
    "status": "Failed",
    "error": "Shift opening has not synced. Sync it first, then retry the unchanged payload.",
    "error_code": "BlockedDependency"
  }
}
```

Lifecycle actions, collections and live corrections can return `status: "Failed", error_code: "DayClosed"`. Completed sales/returns/exchanges are accepted after closing and retain their original business date; they do not require reopening.

Permission and validation errors may use a non-2xx HTTP response instead. Show the server’s error and keep the saved request. Never mark work complete just because it was sent.


## Completed offline bills: acceptance and settlement

This section applies to `create_pos_invoice`, `create_credit_pos_invoice`,
`create_pos_sales_invoice`, and `create_pos_return_invoice`, including exchanges.
The completed .NET bill is the source of its historical amounts. Keep its original
JSON permanently. Store ERP names and reconciliation state separately.

`status: "Success", accepted: true` means ERP permanently accepted the bill.
Posting and accounting reconciliation may still be pending. Do not wait for a
missing credit note or original bill, change the completed bill, or ask the cashier
to complete it again. Exact retries return the original acceptance response with
`duplicate: true`; current state comes from `get_sync_status`.

Completed sale/return APIs use this response when posting is still pending:

```json
{
  "message": {
    "status": "Success",
    "accepted": true,
    "accepted_transaction": "<Retail acceptance record>",
    "settlement_status": "Pending Dependency",
    "duplicate": false
  }
}
```

When posting succeeds immediately, existing invoice response fields remain and
`accounting_outstanding_amount` gives the native outstanding after settlement.
Pending acceptance can have no ERP invoice name yet. States are `Accepted`,
`Posted`, `Pending Dependency`, `Pending Reconciliation`, `Reconciled`, and
`Reconciliation Exception`. These are ERP workflow states, not rejected POS bills.
Malformed payloads, conflicting references, invalid identity/company/customer/
account/currency combinations, and technical corruption may still fail validation.
Changed credit limits, customer balances and closed shifts/days do not reject a
completed bill. Missing shift/session links are retained in the original payload.

### Current status and automatic reconciliation

`get_sync_status` keeps its existing request. Each reference adds `settlement`
with the acceptance record `name`, current `status`, `pos_invoice`,
`sales_invoice`, `current_accounting_outstanding`, and `exception_reason`. Its saved `response` remains the original
acceptance receipt. A pending accepted transaction is already synced.

ERP attempts recovery internally after accepted transactions commit and every five
minutes. The .NET client uses the existing sale/return APIs and the existing
`get_sync_status` API only. No new API call is required for settlement resolution,
and no completed POS payload is edited by recovery.

### Customer views, reports and closing

Customer master/balance responses add `current_receivable`, `available_credit`,
`credit_notes_issued`, `credit_notes_redeemed`, `credit_sales`,
`pending_credit_allocations`, and `unresolved_settlement_amount`.
Current receivable is native ERP accounting including open credits; do not deduct
available credits a second time. Existing dated `current_balance` remains a dated
ledger balance; `current_receivable` is the current accounting position.
Unused credit-note rows include the permanent `external_pos_reference` when
available. Debt-reduction returns are excluded from reusable credit-note lists.

POS Sales Summary, Cashier Wise Sales and POS Daily Closing Summary add requested,
applied and unresolved credit measures. POS Settlement Audit includes pending
relationships and source/destination/reconciliation references. Shift/day/POS
closing records expose separate settlement fields; day closing responses add
`settlement_totals`. Late arrivals refresh derived totals without reopening the
original day or cancelling bills. Issued/redeemed credit is never cash revenue.

POS Settlement Exception records retain Info, Warning, Requires Review or Technical
Error findings. Review these when POS history and current accounting differ.
Foreign-currency/account mismatches remain reviewable reconciliation exceptions;
completed transactions remain accepted while accounting is resolved.

`get_queue_dependencies` is advisory for completed bills: `can_sync` is true even
when the original is absent, with `pending_internal_dependency: true`.
Already accepted pending bills have `already_synced: true`.

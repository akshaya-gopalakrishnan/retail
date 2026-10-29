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
      "printer_name": "Receipt Printer 1",
      "warehouse": "Stores - N"
    },
    "tax_config": {
      "tax_template": "<tax template>",
      "taxes": []
    },
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
    "items": [
      {
        "name": "I-1",
        "item_code": "I-1",
        "item_name": "Example tracked item",
        "stock_uom": "Nos",
        "is_stock_item": 1,
        "has_serial_no": 1,
        "serial_numbers": ["SERIAL-001", "SERIAL-002"],
        "has_batch_no": 1,
        "batches": [
          {
            "batch_no": "BATCH-001",
            "available_qty": 2,
            "expiry_date": "2027-01-31",
            "warehouse": "Stores - N"
          }
        ],
        "current_stock": 2,
        "disabled": 0,
        "packings": []
      }
    ],
    "item_barcodes": [],
    "packing_details": [],
    "item_prices": [],
    "scale_barcode_formats": [],
    "promo_prices": [],
    "buy_x_get_y_promotions": [],
    "gift_voucher_promotions": [],
    "customers": [
      {
        "available_credit": 60.01,
        "bypass_credit_limit_check": 0,
        "credit_limit": 0.0,
        "credit_note_currency": "AED",
        "credit_notes_applied": 0.0,
        "credit_notes_as_of": "2026-10-23 09:49:28.656027",
        "credit_notes_issued": 0.0,
        "credit_notes_redeemed": 0.0,
        "credit_notes_unresolved": 0.0,
        "credit_sales": 0.0,
        "current_receivable": 9580.03,
        "customer_group": null,
        "customer_name": "van 3 customer",
        "gift_vouchers": [],
        "is_credit_customer": 0,
        "loyalty_balances": [
          {
            "as_of_date": "2026-10-23",
            "available_points": 0,
            "conversion_factor": 1.0,
            "currency": "AED",
            "earned_points": 164,
            "expired_points": 154,
            "loyalty_program": "test loyalty",
            "redeemable_amount": 0.0,
            "used_points": 10
          }
        ],
        "loyalty_conversion_factor": 1.0,
        "loyalty_point_entries": [
          {
            "company": "nesto",
            "customer": "C-10",
            "expiry_date": "2026-09-17",
            "invoice": "SI-42",
            "invoice_type": "Sales Invoice",
            "loyalty_points": 157,
            "loyalty_program": "test loyalty",
            "loyalty_program_tier": "Standard",
            "modified": "2026-09-17 11:06:01.107378",
            "name": "LPE-1",
            "posting_date": "2026-09-17",
            "purchase_amount": 3150.0,
            "redeem_against": null
          },
          {
            "company": "nesto",
            "customer": "C-10",
            "expiry_date": "2026-09-17",
            "invoice": "SI-43",
            "invoice_type": "Sales Invoice",
            "loyalty_points": 0,
            "loyalty_program": "test loyalty",
            "loyalty_program_tier": "Standard",
            "modified": "2026-09-17 11:07:58.752980",
            "name": "LPE-2",
            "posting_date": "2026-09-17",
            "purchase_amount": 0.0,
            "redeem_against": null
          },
          {
            "company": "nesto",
            "customer": "C-10",
            "expiry_date": "2026-09-17",
            "invoice": "SI-43",
            "invoice_type": "Sales Invoice",
            "loyalty_points": -10,
            "loyalty_program": "test loyalty",
            "loyalty_program_tier": "Standard",
            "modified": "2026-09-17 11:07:58.770566",
            "name": "LPE-3",
            "posting_date": "2026-09-17",
            "purchase_amount": 0.0,
            "redeem_against": "LPE-1"
          },
          {
            "company": "nesto",
            "customer": "C-10",
            "expiry_date": "2026-10-02",
            "invoice": "SI-70",
            "invoice_type": "Sales Invoice",
            "loyalty_points": 7,
            "loyalty_program": "test loyalty",
            "loyalty_program_tier": "Standard",
            "modified": "2026-10-02 11:51:34.633991",
            "name": "LPE-22",
            "posting_date": "2026-10-02",
            "purchase_amount": 150.04,
            "redeem_against": null
          }
        ],
        "loyalty_program": "test loyalty",
        "loyalty_program_name": "test loyalty",
        "loyalty_program_tier": "Standard",
        "modified": "2026-10-02 11:51:34.654727",
        "name": "C-10",
        "original_debt_reduction": 0.0,
        "pending_credit_allocations": 0.0,
        "promotions_as_of": "2026-10-23",
        "territory": null,
        "unresolved_settlement_amount": 0.0,
        "unused_credit_note_amount": 60.01,
        "unused_credit_notes": [
          {
            "account_currency": "AED",
            "currency": "AED",
            "external_pos_reference": null,
            "receivable_account": "Trade in Opening Fees - N",
            "reference_doctype": "Sales Invoice",
            "reference_name": "VS-10",
            "remaining_amount": 60.01,
            "remaining_amount_in_account_currency": 60.01
          }
        ]
      },
      {
        "available_credit": 0,
        "bypass_credit_limit_check": 0,
        "credit_limit": 0.0,
        "credit_note_currency": "AED",
        "credit_notes_applied": 0.0,
        "credit_notes_as_of": "2026-10-23 09:49:28.656027",
        "credit_notes_issued": 0.0,
        "credit_notes_redeemed": 0.0,
        "credit_notes_unresolved": 0.0,
        "credit_sales": 0.0,
        "current_receivable": 13421.0,
        "customer_group": null,
        "customer_name": "Book Customer",
        "gift_vouchers": [
          {
            "active_from_time": null,
            "active_to_time": null,
            "balance_amount": 50.0,
            "card_archived": 0,
            "card_blocked": 0,
            "company": "nesto",
            "currency": null,
            "customer": "C-7",
            "expiry_date": "2026-09-21",
            "issued_against": "SI-34",
            "issued_against_type": "Sales Invoice",
            "issued_date": "2026-08-22",
            "modified": "2026-08-22 12:55:46.726229",
            "name": "GV-63A410BD",
            "promotion": "AED 50 on buying worth 100",
            "reason": "Expired",
            "redeemed_against": null,
            "redeemed_against_type": null,
            "redeemed_date": null,
            "status": "Unused",
            "use_redemption_hours": 0,
            "valid": false,
            "valid_from": null,
            "voucher_amount": 50.0,
            "voucher_card_batch": null,
            "voucher_code": "GV-63A410BD",
            "voucher_kind": "Promotion Voucher",
            "warehouse": "Stores - N"
          },
          {
            "active_from_time": null,
            "active_to_time": null,
            "balance_amount": 0.0,
            "card_archived": 0,
            "card_blocked": 0,
            "company": "nesto",
            "currency": null,
            "customer": "C-7",
            "expiry_date": "2026-09-21",
            "issued_against": "SI-33",
            "issued_against_type": "Sales Invoice",
            "issued_date": "2026-08-22",
            "modified": "2026-08-22 12:55:46.734969",
            "name": "GV-DC3F2413",
            "promotion": "AED 50 on buying worth 100",
            "reason": "Redeemed",
            "redeemed_against": "SI-34",
            "redeemed_against_type": "Sales Invoice",
            "redeemed_date": "2026-08-22",
            "status": "Redeemed",
            "use_redemption_hours": 0,
            "valid": false,
            "valid_from": null,
            "voucher_amount": 50.0,
            "voucher_card_batch": null,
            "voucher_code": "GV-DC3F2413",
            "voucher_kind": "Promotion Voucher",
            "warehouse": "Stores - N"
          }
        ],
        "is_credit_customer": 0,
        "loyalty_balances": [],
        "loyalty_conversion_factor": 0,
        "loyalty_point_entries": [],
        "loyalty_program": null,
        "loyalty_program_name": null,
        "loyalty_program_tier": null,
        "modified": "2026-07-24 17:10:24.963646",
        "name": "C-7",
        "original_debt_reduction": 0.0,
        "pending_credit_allocations": 0.0,
        "promotions_as_of": "2026-10-23",
        "territory": null,
        "unresolved_settlement_amount": 0.0,
        "unused_credit_note_amount": 0.0,
        "unused_credit_notes": []
      },
      {
        "available_credit": 0,
        "bypass_credit_limit_check": 0,
        "credit_limit": 0.0,
        "credit_note_currency": "AED",
        "credit_notes_applied": 0.0,
        "credit_notes_as_of": "2026-10-23 09:49:28.656027",
        "credit_notes_issued": 0.0,
        "credit_notes_redeemed": 0.0,
        "credit_notes_unresolved": 0.0,
        "credit_sales": 0.0,
        "current_receivable": 22022.0,
        "customer_group": null,
        "customer_name": "customer 1",
        "gift_vouchers": [],
        "is_credit_customer": 0,
        "loyalty_balances": [],
        "loyalty_conversion_factor": 0,
        "loyalty_point_entries": [],
        "loyalty_program": null,
        "loyalty_program_name": null,
        "loyalty_program_tier": null,
        "modified": "2026-06-16 16:45:52.810360",
        "name": "C-1",
        "original_debt_reduction": 0.0,
        "pending_credit_allocations": 0.0,
        "promotions_as_of": "2026-10-23",
        "territory": null,
        "unresolved_settlement_amount": 0.0,
        "unused_credit_note_amount": 0.0,
        "unused_credit_notes": []
      }
    ],
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
      },
      {
        "name": "Loyalty",
        "type": "Loyalty",
        "enabled": 1,
        "modified": "2026-09-30 09:00:00",
        "is_settlement": 1
      },
      {
        "name": "Promotion Voucher",
        "type": "Promotion Voucher",
        "enabled": 1,
        "modified": "2026-09-30 09:00:00",
        "is_settlement": 1
      },
      {
        "name": "Voucher Card",
        "type": "Voucher Card",
        "enabled": 1,
        "modified": "2026-09-30 09:00:00",
        "is_settlement": 1
      }
    ],
    "counters": []
  }
}
```

The three customer rows above are original local-site snapshots from `retail-test.localhost` (2026-10-23): `C-10` shows loyalty entries and unused credit, `C-7` shows customer-linked vouchers, and `C-1` shows empty promotion lists. Existing customer and credit fields are included unchanged. The surrounding master-envelope values are illustrative. For current loyalty/voucher balances for every customer, omit `modified_after` when refreshing masters; see [Customer master: loyalty and customer vouchers](#customer-master-loyalty-and-customer-vouchers-additive).

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

For .NET POS sales, send the selected barcode on each item row. Retail resolves the invoice name by Item Code + Barcode against that Item's packing rows. Only when barcode is missing, a packing sale's name is generated as original Item name + sold UOM + conversion factor (for example `Aqua Fresh Water 1.5 ltr - Pack x4`). Stock-unit sales with factor 1 retain the original name. A present unmatched barcode does not trigger this generated fallback; the submitted `item_name`, when supplied, is retained, otherwise the original Item name is used. This affects display identity only, not quantities or financial values.

Retail reports also add sold/transaction UOM, recorded barcode, packing name and sold quantity for ERP and .NET transactions. Item-detail rows use the exact source line; grouped rows show a packing breakdown. New submissions retain a Retail-owned identity snapshot. Missing historical barcodes remain "Not recorded"; the request payload and existing financial calculations are unchanged. See [Transaction identity in reports](TRANSACTION_IDENTITY_REPORTS.md) for coverage and historical-data rules.

Save changed records without deleting records missing from a changes-only reply. Replace each returned item's full `packings` list and the full `scale_barcode_formats` list. Refresh all masters regularly because permission and customer-balance changes may not appear in a changes-only download.

### Set cashier PIN

`POST /api/method/retail.api.pos_sync.set_cashier_quick_pin`

Super Admin, or Customer Administrator for their managed staff only. Customer Administrators need POS module access, Employee List and POS Cashier Shifts access, and Employee write permission. System Manager alone does not authorize PIN setup. Keep PINs as text so leading zeros remain.

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
    {"item_code": "MILK", "serial_no": null, "batch_no": null, "uom": "Nos", "conversion_factor": 1, "qty": 2, "rate": 10, "rate_includes_vat": 0, "amount": 20, "net_amount": 20, "vat_rate": 0, "vat_amount": 0},
    {"item_code": "MILK", "uom": "Nos", "conversion_factor": 1, "qty": -1, "rate": 10, "rate_includes_vat": 0, "amount": -10, "net_amount": -10, "vat_rate": 0, "vat_amount": 0, "serial_no": null, "batch_no": null}
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

Send the billed prices, VAT, discounts and totals unchanged. Item `discount_amount` is per unit and is preserved exactly in the POS invoice/report. Header `discount_amount` is the reported bill discount summary; it is not applied again as an additional ERP deduction. `amount` is the pre-discount line value in the same VAT basis as `rate` (`rate_includes_vat`); ERP maps it into VAT-exclusive amount fields. `net_amount` is after all discounts, excluding VAT. Explicit final net amounts, VAT and payable totals govern accounting; original values remain in the immutable payload. ERP permanently accepts the completed sale and posts it when accounting is available. Do not create a second invoice or payment for it.

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
      "serial_no": null,
      "batch_no": null,
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
      "serial_no": null,
      "batch_no": null,
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
      "serial_no": null,
      "batch_no": null,
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

### Add promotions to the existing payments (offline)

Use the existing `POST /api/method/retail.api.pos_sync.create_pos_invoice` and its
existing payload. Cash/card rows, `credit_note_redemptions`, `credit_sale_amount`,
item amounts, VAT and completed-sale references keep their existing meaning.
No format/version flag, new invoice endpoint or online approval is required.

**Only three payment choices are added inside `payments`:**

| Added `mode_of_payment` | `reference_no` | Extra value |
|---|---|---|
| `Loyalty` | Selected customer's downloaded `loyalty_program` ID | `points`: the whole-number count used offline. `amount` is its actual POS money value. |
| `Promotion Voucher` | Customer `gift_vouchers[].voucher_code` or scanned promotion-voucher code | None. |
| `Voucher Card` | Scanned/entered card code from the downloaded voucher-card snapshot | None. |

The existing `modes_of_payment` master array additionally lists these three choices.
Keep existing cash/card MOP names and references unchanged. Keep credit-note
allocations in `credit_note_redemptions` and the unpaid portion in
`credit_sale_amount`; do not move them into a new format or duplicate them in payments.

.NET completes the sale offline from downloaded data, retains the original bill and
uploads it at end of day. It does not call the online voucher approval API for
these added rows. No `redemption_reference` is sent. Use the same original
`external_pos_reference` and unchanged payment-row order/content on retries.

In this example the POS recorded a 500 invoice and used vouchers as payment:

```text
500 = cash 100 + card 50 + loyalty 50 + promotion voucher 50
    + voucher card 50 + existing credit-note redemption 50 + unpaid credit 150
```

Send the actual recorded item prices, ordinary discounts, VAT and invoice total;
ERP does not deduct promotion payment rows a second time. Earlier discounted-voucher
payloads retain their existing meaning and are shown separately below.

Complete request example (illustrative IDs; these benefits do not belong to one
actual customer; zero VAT and money value 1 per loyalty point):

```json
{
  "external_pos_reference": "KARAMA-C001-T001-SALE-20261023-000500",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20261023-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20261023-000001",
  "business_date": "2026-10-23",
  "customer": "C-EXAMPLE",
  "posting_date": "2026-10-23",
  "posting_time": "10:30:00",
  "pos_bill_no": "000500",
  "pos_local_created_at": "2026-10-23 10:30:00",
  "update_stock": 1,
  "discount_amount": 0,
  "net_total": 500,
  "vat_amount": 0,
  "grand_total": 500,
  "items": [
    {
      "item_code": "I-1",
      "serial_no": null,
      "batch_no": null,
      "qty": 1,
      "uom": "Nos",
      "conversion_factor": 1,
      "rate": 500,
      "rate_includes_vat": 0,
      "discount_amount": 0,
      "amount": 500,
      "net_amount": 500,
      "vat_rate": 0,
      "vat_amount": 0
    }
  ],
  "payments": [
    {
      "mode_of_payment": "Cash",
      "amount": 100,
      "reference_no": ""
    },
    {
      "mode_of_payment": "Card",
      "amount": 50,
      "reference_no": "CARD-000500"
    },
    {
      "mode_of_payment": "Loyalty",
      "amount": 50,
      "reference_no": "test loyalty",
      "points": 50
    },
    {
      "mode_of_payment": "Promotion Voucher",
      "amount": 50,
      "reference_no": "GV-EXAMPLE"
    },
    {
      "mode_of_payment": "Voucher Card",
      "amount": 50,
      "reference_no": "CARD-EXAMPLE"
    }
  ],
  "issued_vouchers": [],
  "credit_note_redemptions": [
    {
      "credit_note_external_reference": "KARAMA-C001-T001-RETURN-20261022-000123",
      "amount": 50
    }
  ],
  "credit_sale_amount": 150
}
```

ERP posts the new promotion amounts through server-owned promotion accounts, not
the cashier's cash/bank accounts. It deducts the intended voucher amounts and points
once, including an audited overdraft when a known same-company source has less
balance than the completed POS used. Expiry, blocked status, product eligibility,
customer enrollment, customer link and conversion changes are audit comparisons;
they do not reject this completed sale or rewrite the original payment split.

For example: voucher payment 50 with current balance 30 is retained as a 50 payment;
the known voucher source records balance -20 and the audit shows the 20 shortage.
The customer's explicitly recorded credit remains 150. A source that cannot be
found, or belongs to another company, is preserved as an intended redemption in the
durable operation receipt and audit; no fictitious source is created and another
company's ledger is not changed. Monetary settlement of the sale still proceeds.

If the portions themselves differ from the recorded total, ERP adds an explicitly
identified internal `Promotion Variance` accounting row and audit entry. It does
not alter the downloaded/uploaded JSON, turn the difference into cash or silently
increase the intended customer credit. .NET does not send a variance row.

Audit findings appear in the existing **External POS Rate Audit** with source
reference, payment-row details, original POS amount/points, ERP comparison and
reason. Each source movement has an internal immutable **POS Promotion Redemption**
receipt. Exact retries cannot deduct balances again. Technical/database posting
failures retain the completed bill for existing internal recovery; a retained
acceptance is not a claim that accounting has posted.

Response fields are unchanged. With the example fully posted and its existing
credit-note allocation applied, `grand_total` is 500, POS `outstanding_amount` is
200 before credit-note allocation, and `accounting_outstanding_amount` is 150.
Native payment totals include the new promotion tenders; cash/card is still only
100/50 in the corresponding actual tender rows.

This addition applies to sale payloads. Exchange payloads retain their existing
supported payment combinations. Returns against these new promotion-tender sales
are retained for allocation review to avoid refunding redeemed benefits as cash.
Existing sales without these new tenders retain their return, credit-note allocation
and credit-sale behavior. Do not combine a promotion payment row with
another redemption field for the same benefit.

Copyable payload: [`retail/docs/pos-mixed-payment-sale-example.json`](retail/docs/pos-mixed-payment-sale-example.json).

### Earlier mixed-payment implementation: separate fields and online voucher approvals

This separate-field format remains supported unchanged for existing callers.
Offline promotion payment rows are the additive option documented above. Its copyable example is
[`retail/docs/pos-mixed-payment-legacy-example.json`](retail/docs/pos-mixed-payment-legacy-example.json).


Use the existing `POST /api/method/retail.api.pos_sync.create_pos_invoice`.
No new invoice endpoint and no separate invoice per tender.

| Send here | Include |
|---|---|
| `payments[]` | Actual tender rows: Cash, Card, bank transfer, cheque or another ERP payment mode configured for the counter. Use the exact downloaded mode name. |
| `loyalty_redemption` | One object: `loyalty_program`, positive whole-number `points`, and money `amount`. Omit when unused. Accounts and conversion validation are server-owned. |
| `voucher_redemptions[]` | One row per approved promotion voucher or voucher card: `voucher_code`, `amount`, `redemption_reference`. The server identifies the voucher type from its code. Use `[]` when unused. |
| `credit_note_redemptions[]` | Existing credit-note reference/amount rows. Use `[]` when unused. |
| `credit_sale_amount` | Remaining unpaid customer amount. Use `0` when fully settled. |

**Amount rule:** vouchers retain the existing discount treatment. First subtract
voucher benefits from `bill_total_before_vouchers` to obtain `grand_total`.
Send final item net amounts and VAT that agree with that discounted total; do not
subtract vouchers a second time or add them to `payments`.

```text
500 before vouchers - 50 promotion voucher - 50 voucher card = 400 grand_total
400 = 100 cash + 50 card + 50 loyalty + 50 credit-note redemption + 150 unpaid credit
```

With a nonempty `voucher_redemptions`, send `bill_total_before_vouchers`.
`rounded_total`, when supplied, is the final payable total for settlement checking.
The example assumes zero VAT and a program worth AED 1 per point. For taxed sales,
.NET sends its actual final per-item net/VAT values and the original completed totals.

Before finishing a voucher sale, approve **each voucher** using the existing
`retail.api.gift_vouchers.redeem_gift_voucher` API, with the same sale
`external_pos_reference` and a different `redemption_reference` for each voucher.
For cards, include `bill_total` and the eligible `items` as in the existing card
redemption example. Put the returned references in the single invoice below.
Invoice sync links approvals; it never debits vouchers again. Exact retries use
unchanged sale/approval references. The approval calls remain online. If checkout
is abandoned after approval, reverse each approval with the existing
`reverse_gift_voucher_redemption` API before discarding the bill.

Request JSON (illustrative IDs; replace with actual downloaded/configured values):

```json
{
  "external_pos_reference": "KARAMA-C001-T001-SALE-20261023-000500",
  "branch": "Karama",
  "counter_code": "C001",
  "pos_terminal_id": "T001",
  "cashier_employee": "E-1",
  "external_shift_reference": "KARAMA-C001-T001-SHIFT-20261023-000001",
  "external_session_reference": "KARAMA-C001-T001-SESSION-20261023-000001",
  "business_date": "2026-10-23",
  "customer": "C-1",
  "posting_date": "2026-10-23",
  "posting_time": "10:30:00",
  "pos_bill_no": "000500",
  "pos_local_created_at": "2026-10-23 10:30:00",
  "update_stock": 1,
  "bill_total_before_vouchers": 500,
  "discount_amount": 100,
  "net_total": 400,
  "vat_amount": 0,
  "grand_total": 400,
  "items": [
    {
      "item_code": "I-1",
      "serial_no": null,
      "batch_no": null,
      "qty": 1,
      "uom": "Nos",
      "conversion_factor": 1,
      "rate": 500,
      "rate_includes_vat": 0,
      "discount_amount": 100,
      "amount": 400,
      "net_amount": 400,
      "vat_rate": 0,
      "vat_amount": 0
    }
  ],
  "payments": [
    {
      "mode_of_payment": "Cash",
      "amount": 100,
      "reference_no": "CASH-000500"
    },
    {
      "mode_of_payment": "Card",
      "amount": 50,
      "reference_no": "CARD-000500"
    }
  ],
  "loyalty_redemption": {
    "loyalty_program": "Customer Rewards",
    "points": 50,
    "amount": 50
  },
  "voucher_redemptions": [
    {
      "voucher_code": "PGV-0123456789ABCDEF0123456789ABCDEF",
      "amount": 50,
      "redemption_reference": "KARAMA-C001-T001-REDEEM-20261023-000500-PROMO"
    },
    {
      "voucher_code": "A7K2M",
      "amount": 50,
      "redemption_reference": "KARAMA-C001-T001-REDEEM-20261023-000500-CARD"
    }
  ],
  "credit_note_redemptions": [
    {
      "credit_note_external_reference": "KARAMA-C001-T001-RETURN-20261022-000123",
      "amount": 50
    }
  ],
  "credit_sale_amount": 150,
  "issued_vouchers": []
}
```

Response example after successful posting and credit-note allocation:

```json
{
  "message": {
    "status": "Success",
    "accepted": true,
    "accepted_transaction": "<accepted transaction ID>",
    "settlement_status": "Reconciled",
    "pos_invoice_name": "POS-1",
    "invoice_name": "POS-1",
    "doctype": "POS Invoice",
    "docstatus": 1,
    "grand_total": 400,
    "outstanding_amount": 200,
    "accounting_outstanding_amount": 150,
    "issued_vouchers": [],
    "rate_audit_rows": [],
    "audit_warnings": []
  }
}
```

`outstanding_amount` is the POS receipt remainder **before** the separate credit-note
allocation (200). `accounting_outstanding_amount` is the remaining accounting debt
**after** that allocation (150). Native ERP `paid_amount` includes loyalty: here it
is 200, while the actual cash/card tender rows total 150. Never count loyalty again
as cash, or subtract credit notes twice.

`accepted: true` retains the completed bill; it does not alone prove posting.
Missing/reversed/mismatched approvals or unavailable loyalty balances keep the bill
for reconciliation without silently substituting cash, write-offs or customer debt.
Use existing `get_sync_status` and the accepted transaction status to monitor recovery.
Loyalty debits use locked customer point buckets and post once; merged accounting
does not consume the points again.

The legacy singular `voucher_redemption` remains supported with its existing
meaning. Send it **or** `voucher_redemptions`, never both. Existing invoice fields
and responses remain supported. Do not put loyalty, vouchers, credit-note redemption,
or unpaid customer credit in cash/card tender rows.

This extension covers sales, including sales with zero cash/card. Exchange receipts
and redemption objects on return requests are not supported. Returns against a new
loyalty-redemption sale are retained for review rather than automatically refunding
money or deleting redeemed points; proportional loyalty return allocation needs
separate handling. Other existing return payloads keep their current behavior.

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
      "serial_no": null,
      "batch_no": null,
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
      "serial_no": null,
      "batch_no": null,
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
      "serial_no": null,
      "batch_no": null,
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

### Customer master: loyalty and customer vouchers (additive)

The existing `get_pos_master_data` → `customers` rows retain all original customer,
credit-limit, unused-credit-note and settlement fields. Each row additionally has:

| Field | Meaning |
|---|---|
| `loyalty_program`, `loyalty_program_name`, `loyalty_program_tier` | Assigned program in the counter company; null when none. |
| `loyalty_conversion_factor` | Money per point; zero without an assigned program. |
| `loyalty_balances` | One row per customer/program with `earned_points`, `used_points`, `expired_points`, `available_points`, `conversion_factor`, `redeemable_amount`, `currency`, `as_of_date`. Includes a zero balance for an assigned program without entries. |
| `loyalty_point_entries` | Full company-scoped customer point history, with program/tier, points, purchase amount, posting/expiry dates, redemption linkage, invoice type/reference and modified timestamp. |
| `gift_vouchers` | Only vouchers directly linked to this customer and company: code/ID, original value, remaining balance, status, issue/expiry dates, promotion, issue/redemption invoice references, company/warehouse, currency and card controls. `valid`/`reason` reflect current usability. |
| `promotions_as_of` | Server date for this snapshot. |

Replace these lists for each returned customer; empty lists clear old local data.
Balances are per program; do not combine points from different programs. A balance
for an old program does not enroll the customer in that program. Voucher warehouse
and eligibility restrictions still apply; voucher redemption remains subject to the
existing validation/API. These snapshots do not reserve points or voucher money.
General promotions, customer-specific pricing rules and schemes are not added here.

Customer selection still follows the existing `modified_after` filter on Customer.
Point/voucher changes and expiry do not necessarily modify Customer: request a full
master refresh (omit `modified_after`) to refresh all customer promotion balances.

Original local customer payload, including the existing fields and these additions:
[`retail/docs/pos-customers-local-sample.json`](retail/docs/pos-customers-local-sample.json).
This is a read-only capture from `retail-test.localhost`, company `nesto`; its
`message.customers` is the customer section of the master response, not a new endpoint.

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

### Dates, hours and scope for .NET

The three promotion downloads below and `get_pos_master_data` include the new
schedule fields. Master data returns `promo_prices`, `buy_x_get_y_promotions`,
and `gift_voucher_promotions`. Promo Price and Buy X Get Y use the master
`modified_after` filter; gift voucher promotions remain a full scoped snapshot.
The response also includes `server_timezone` (for example `Asia/Dubai`). Use
this timezone to interpret the sale time and the promotion hours.

| JSON field | Format / meaning |
| --- | --- |
| `active_from`, `active_to` | Separate date values: `yyyy-MM-dd` or `null` for an unrestricted boundary. |
| `active_from_time`, `active_to_time` | Separate daily time values: `HH:mm:ss` or `null` for an unrestricted boundary. Midnight is `00:00:00`, not null. |
| `promotion_scope` | Promo Price: `ITEM`, `CATEGORY`, `BRAND`, or `WHOLE BILL`. Buy X Get Y: `ITEM`, `CATEGORY`, or `BRAND` for Buy Item rows. |
| Product `item`, `item_group`, `brand` | Target Item, Category (Item Group), or Brand, according to the selected scope. |
| Product `matching_item_groups` | Category names including the selected Category and all descendants. Empty for Item, Brand and Whole Bill rows. |

Apply promotions to the bill's original sale date/time in `server_timezone`:

- Dates only: valid all day within the dates, including both boundary dates.
- Times only: recur daily, with no date restriction.
- Both: the daily time window applies on every date in the date range.
- Both time boundaries are inclusive. If the end is earlier than the start,
  the window crosses midnight: `22:00:00`–`02:00:00` matches 23:00 and 01:00.
- A null start or end is unrestricted on that side. Do not convert null to
  midnight, today's date, or zero.
- Skip `disabled: 1` Promo Price/Buy X Get Y offers and `enabled: 0` voucher
  offers. Keep existing company, warehouse, quantity, value, price-list,
  priority and free-item rules.

For Promo Price and Buy X Get Y Buy Item rows, use only the selected scope (WHOLE BILL applies only to Promo Price):

| `promotion_scope` | How .NET matches the product row |
| --- | --- |
| `ITEM` | Match the downloaded Item code against `products[].item`. |
| `CATEGORY` | Match the Item master’s `item_group` against `products[].matching_item_groups`, which includes the selected Category and all descendants. |
| `BRAND` | Match `products[].brand` against the Item master's `brand`. |
| `WHOLE BILL` | One product row applies to all eligible bill items; Item, Category and Brand targets are blank. Apply the row's discount or price once per eligible item, without an additional bill header discount. |

Gift voucher `excluded_item_groups` rows also include `matching_item_groups`.
Exclude an Item when its Item master `item_group` occurs in any of these lists.
For example, `{"item_group":"Beverages","matching_item_groups":["Beverages","Juice"]}`
excludes both categories. This is a snapshot of the category tree; refresh the
full promotion download after reorganizing categories.

Example targets: ITEM `{ "item": "ITEM-001", "item_group": "", "brand": "" }`;
CATEGORY `{ "item": "", "item_group": "Beverages", "brand": "" }`;
BRAND `{ "item": "", "item_group": "", "brand": "Example Brand" }`;
WHOLE BILL `{ "item": "", "item_group": "", "brand": "" }`.

After updating the .NET response models and promotion matching, do one full
promotion download **without `modified_after`** to refresh existing cached
rules. Full downloads include disabled, expired, future and undated records;
filter eligibility locally. Incremental replies update records by `name` and
include changes that disable or expire a rule. Never reprice completed bills.


### Download special prices and other promotions

`GET /api/method/retail.api.pos_sync.get_pos_promo_prices?branch=Karama&counter_code=C001`

Each `promotions[].products[]` row includes `barcode` (the saved promotion/packing
barcode, falling back to the Item barcode), `has_serial_no` (0 or 1), and
`serial_numbers` (active serial IDs in the counter's warehouse, or `[]`).
Category/brand-only rows have no item barcode or serials. These fields are
snapshots for the returned offers; `modified_after` still filters promotions.
Use the item master download to refresh serial availability independently of
promotion changes. Downloaded serials are not reserved.

Existing `gift_voucher_ledger[]` rows also include `barcode` (the scannable
`voucher_code`, falling back to `name`) and `serial_no` (the saved `card_number`,
or `null` when unnumbered). Existing voucher fields remain unchanged; the serial
number is a sequence within its voucher card batch.

Product rows in POS master data, combined/standalone promotion downloads and
warehouse stock snapshots include `barcode`, `has_serial_no`, `serial_no` and
`serial_numbers`, including nested packing, price, rule and eligibility rows.
Saved row barcodes and selected `serial_no` values are preserved. Otherwise
`barcode` falls back to the Item barcode and `serial_no` is an empty string.
`serial_numbers` contains active serial IDs in the counter warehouse (`[]` for
unserialized, disabled or unavailable items). `item_name` is added when absent.
These are additions to existing rows, not separate payloads or reservations.

Optional `modified_after`. Keep a separate saved time for each API. Apply the returned dates, scope and disabled flags; do not recalculate saved bills. The full download includes disabled, expired, future and undated promotions. Incremental downloads include modified records, so the POS can replace or disable its cached rules.

Request body: none; use the URL values above.

Response sections:

| Response array | Contents |
| --- | --- |
| `promotions` | Existing Promo Price payload, unchanged. |
| `buy_x_get_y_promotions` | Buy/free quantities, same-product flag, qualifying scope and Buy Item/Free Item rows. |
| `gift_voucher_promotions` | Qualifying spend, voucher value, multiplication, expiry days and excluded categories. |
| `loyalty_programs` | Program dates, customer eligibility, conversion factor and earning tiers. Includes future/expired programs; check dates locally. |
| `loyalty_point_entries` | Full company snapshot of signed ledger entries, with earned/used/expired/available totals for each entry's customer/program. |
| `loyalty_snapshot` | Snapshot metadata: `mode: "full"`, company and balance date. |
| `voucher_card_batches` | Card values, quantities, activation dates/times, restrictions, logo and terms. |
| `gift_voucher_ledger` | Card and promotion voucher codes, amounts, balances, status, eligibility, customers and references. |
| `voucher_snapshot` | Full voucher snapshot scope, timestamp and timezone. |
| `pricing_rules` | Selling Pricing Rules with native ERP fields, item/category/brand targets, customer restrictions, price/product rewards and scheme references. |
| `promotional_schemes` | Selling Promotional Scheme configuration, including target tables and price/product slabs. Informational; apply its eligible Pricing Rules instead. |

Promotion/program arrays use this request's company/warehouse context and
`modified_after`. Full downloads retain disabled, expired and future records.
Store each rule array separately by `name`, upsert incremental records, and
check eligibility on each new bill. An empty incremental rule array does not
mean delete cached rules. Replace `loyalty_point_entries`, `voucher_card_batches`
and `gift_voucher_ledger` on every download, including incremental requests;
empty snapshots clear their cached rows. Save
`server_time` only after successfully storing **all** arrays. Download once
without `modified_after` when adding these new arrays. Category-tree changes
require another full refresh. The standalone APIs retain their existing payloads.

Pricing Rules and Promotional Schemes retain native `disable`, `valid_from`,
`valid_upto` and other rule fields; added `enabled`/`disabled` are normalized
flags. `promotion_version` identifies the downloaded rule. `apply_in_pos: 0`
means **do not apply this record as an additional offer**. Every scheme is
informational (`apply_in_pos: 0`). Rules generated from a currently linked
Promo Price or Buy X Get Y offer also have `apply_in_pos: 0`, with
`source_promotion_type` and `source_promotion`, because that offer is already
in its dedicated array. Independent selling rules have `apply_in_pos: 1`;
this is not proof of eligibility: still check disabled status, dates, customer,
price list, quantities, currency, conditions, priority and stacking rules.
Do not apply both a scheme's slabs and its generated rules. Historical retired
rules may have `apply_in_pos: 1` but remain ineligible through `disabled: 1`.
Category targets in native `item_groups` include `matching_item_groups`;
`other_item_group` has `other_matching_item_groups` when populated.

This is a rule download, not an implementation of every ERP pricing condition
inside .NET. If the terminal cannot implement a native condition or cumulative
rule faithfully, it must not silently treat it as an unconditional discount.
Loyalty balance/earning/redemption transaction support is separate from this
program download; no new loyalty spending flow is introduced here.

#### Customer loyalty points in this same download

Customer/program totals repeat on each ledger entry; there is no separate balance array.

- `loyalty_point_entries`: entry ID (`name`), `customer` (ERP customer ID),
  `loyalty_program`, tier, company, signed `loyalty_points`, `purchase_amount`,
  posting/expiry dates, `redeem_against`, source invoice type/ID and `modified`.
  Positive earning rows, negative redemption rows and positive restoration
  movements are preserved. Entries are scoped to the counter's **company**;
  points are not restricted to the issuing warehouse.
- Each entry also includes `earned_points`, `used_points`, `expired_points`,
  `available_points` and `as_of_date`. These are **customer/program totals**
  across the snapshot, not totals for that one entry. The same totals repeat
  on every row sharing `(company, customer, loyalty_program)`. Read them from
  any one row per group; **do not sum these repeated totals across entries**.
  Original signed `loyalty_points`, entry identity, tier and invoice fields
  remain unchanged. Only actual ledger entries are returned: customers with
  no entries have no row, and no synthetic ledger entries are created.
- `earned_points`: total original positive earning buckets posted on or before
  `as_of_date`, including subsequently used/expired buckets. Restoration rows
  do not count as new earnings. Future-posted earning buckets are excluded.
- `used_points`: net points consumed against those earning buckets, after
  subtracting linked point restorations. Movements are matched through
  `redeem_against`, within the same customer/program, using the same movement
  treatment as the existing Retail available-balance calculation.
- `expired_points`: the unused remainder of expired earning buckets after
  their redemptions/restorations. Spent points are not also counted as expired.
  Expiry is strictly before `as_of_date`; points expiring today remain available
  under the existing Retail rule.
- For normal dated earning buckets, `earned_points - used_points -
  expired_points = available_points`. A bucket with no expiry date counts as
  earned, but current Retail rules exclude it from available points; it is not
  falsely labelled expired. Such legacy data may not reconcile using only
  these four totals. No existing availability calculation is changed.
- `available_points` uses the existing Retail bucket calculation, not a raw
  sum of ledger points. It includes signed movements against their earning
  bucket, excludes expired and future-posted earning buckets, and retains
  the current Retail behaviour that a missing expiry date is not spendable.
  Program validity/enrolment must still be checked; a historical balance
  does not authorize redemption.
- `loyalty_snapshot.mode` is `full` even when `modified_after` is supplied.
  Replace the cached entries for `loyalty_snapshot.company` atomically after
  a successful download, and refresh customer totals from the resulting rows.
  An empty entries array clears that company's cached entries/totals; do not
  clear another company's cache. If a previously cached customer/program no
  longer has entries in the full snapshot, clear its old totals too.
  This handles entries deleted by cancellation and balances changing through
  expiry without any row's modified timestamp changing. Other promotion
  arrays continue to follow their existing incremental-upsert rules.

These are balance snapshots for display/reconciliation, not a new redemption
approval or offline-spending API. Refresh before relying on a displayed balance;
concurrent sales can change points after download. Existing completed-sale
and loyalty transaction handling is unchanged.

Actual local example on 2026-10-22: customer `C-10` has an earning entry of
157 and a redemption movement of -10 against it, but that earning bucket
expired on 2026-09-17. Another earning entry of 7 expired on 2026-10-02.
Therefore customer `C-10` has `earned_points: 164`, `used_points: 10`,
`expired_points: 154`, and `available_points: 0`. The expired total is the
unused remainder (147 + 7), not the full original earnings.
The local snapshot contains 5 actual ledger entries. Each `C-10` entry carries
the same four customer/program totals above.

Response example (existing fields retained; new fields are additive):

```json
{
  "message": {
    "status": "Success",
    "server_time": "2026-10-14 09:00:00",
    "server_timezone": "Asia/Dubai",
    "branch": "Karama",
    "counter": "Karama-C001",
    "counter_code": "C001",
    "promotions": [
      {
        "name": "Chicken offer",
        "promotion_version": "9aee4b401956750a4a3f31583fa74c0697fa4014e8e159cb17f37cb540571305",
        "description": "Chicken offer",
        "enabled": 1,
        "disabled": 0,
        "active_from": "2026-10-14",
        "active_to": "2026-10-31",
        "active_from_time": "09:00:00",
        "active_to_time": "12:00:00",
        "promotion_scope": "ITEM",
        "company": "Example Company",
        "warehouse": "Stores - EC",
        "min_qty": 1,
        "max_qty": 10,
        "min_sales_value": 0,
        "priority": "1",
        "notes": "Offer while stocks last",
        "modified": "2026-10-14 08:00:00",
        "products": [
          {
            "name": "example-product-row",
            "idx": 1,
            "item": "ITEM-001",
            "item_group": "",
            "brand": "",
            "matching_item_groups": [],
            "barcode": "BC0048800",
            "qty": 1,
            "uom": "Nos",
            "price_list": "Standard Selling",
            "current_price": 9.52,
            "current_price_including_tax": 10.0,
            "purchase_price": 4.76,
            "purchase_price_including_tax": 5.0,
            "vat_rate": 5,
            "discount_input": "Amount",
            "discount_amount": 1.0,
            "discount_percent": 10.0,
            "promo_price": 0,
            "promo_price_including_tax": 0,
            "calculated_promo_price": 8.57,
            "calculated_promo_price_including_tax": 9.0,
            "max_qty": 5
          }
        ]
      }
    ],
    "buy_x_get_y_promotions": [
      {
        "name": "Buy 2 tea + Get 1 Muffin free",
        "promotion_version": "3ef692236041a0618b77cd14fffeaf11735dfbb0cdf15966efe5aef1b1a73eb4",
        "description": "Buy 2 tea + Get 1 Muffin free",
        "enabled": 1,
        "disabled": 0,
        "active_from": "2026-08-21",
        "active_to": "2026-08-22",
        "active_from_time": "08:50:31",
        "active_to_time": "15:50:34",
        "company": "nesto",
        "warehouse": "Stores - N",
        "modified": "2026-10-15 09:10:12.067501",
        "promotion_scope": "ITEM",
        "buy_qty": 2.0,
        "free_qty": 1.0,
        "same_product_only": 0,
        "priority": "10",
        "products": [
          {
            "add_to": "Buy Item",
            "item": "I-27",
            "item_name": "Tea",
            "barcode": "BC696861983",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "item_group": "",
            "brand": null,
            "matching_item_groups": [],
            "uom": "Nos"
          },
          {
            "add_to": "Free Item",
            "item": "I-23",
            "item_name": "Chocolate Muffin",
            "barcode": "muf123",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "item_group": "",
            "brand": null,
            "matching_item_groups": [],
            "uom": "Nos"
          }
        ]
      }
    ],
    "gift_voucher_promotions": [
      {
        "name": "AED 50 on buying worth 100",
        "promotion_version": "04d3556e19b790e7d247f7d4385dbcd709d4a235e98ee22607ba4d317d37a59e",
        "description": "AED 50 on buying worth 100",
        "enabled": 1,
        "disabled": 0,
        "active_from": "2026-08-22",
        "active_to": "2026-08-23",
        "active_from_time": null,
        "active_to_time": null,
        "company": "nesto",
        "warehouse": "Stores - N",
        "modified": "2026-08-22 10:52:16.118598",
        "min_sales_value": 100.0,
        "voucher_amount": 50.0,
        "multiply_with_sales_amount": 0,
        "expiry_days": 30,
        "excluded_item_groups": [
          {
            "item_group": "sugary drinks",
            "matching_item_groups": [
              "sugary drinks"
            ]
          }
        ]
      }
    ],
    "loyalty_programs": [
      {
        "auto_opt_in": 1,
        "collection_rules": [
          {
            "collection_factor": 20.0,
            "idx": 1,
            "min_spent": 0.0,
            "name": "qcu2gbp85u",
            "tier_name": "Standard"
          }
        ],
        "company": "nesto",
        "conversion_factor": 1.0,
        "cost_center": "Main - N",
        "customer_group": "All Customer Groups",
        "customer_territory": "All Territories",
        "expense_account": "Consultancy Fees - N",
        "expiry_duration": 0,
        "from_date": "2026-09-17",
        "loyalty_program_name": "test loyalty",
        "loyalty_program_type": "Single Tier Program",
        "modified": "2026-09-17 10:37:03.823201",
        "name": "test loyalty",
        "project": null,
        "to_date": "2027-09-17"
      }
    ],
    "pricing_rules": [
      {
        "name": "PRLE-0002",
        "promotion_version": "b9e6157ef9e236ff5c7f1033075a35e2bf576fe7b96052445af4c2ac99e8ac77",
        "enabled": 1,
        "disabled": 0,
        "apply_in_pos": 1,
        "selling": 1,
        "company": "nesto",
        "warehouse": null,
        "valid_from": "2026-07-08",
        "valid_upto": "2026-07-09",
        "apply_on": "Item Code",
        "price_or_product_discount": "Product",
        "min_qty": 5.0,
        "free_qty": 1.0,
        "same_item": 0,
        "free_item": "I-1",
        "free_item_uom": "Nos",
        "free_item_rate": 0.0,
        "apply_rule_on_other": "Item Code",
        "other_item_code": "I-1",
        "other_item_group": null,
        "other_brand": null,
        "is_recursive": 0,
        "is_cumulative": 1,
        "promotional_scheme": "5maggi+ 1 water free",
        "items": [
          {
            "item_code": "I-9",
            "uom": "Nos"
          }
        ]
      }
    ],
    "promotional_schemes": [
      {
        "name": "5maggi+ 1 water free",
        "promotion_version": "bd05bccee138395598be11ee0c22f6f0810d739e712ea05817999dd48eea92dd",
        "enabled": 1,
        "disabled": 0,
        "apply_in_pos": 0,
        "selling": 1,
        "company": "nesto",
        "valid_from": "2026-07-08",
        "valid_upto": "2026-07-09",
        "apply_on": "Item Code",
        "apply_rule_on_other": "Item Code",
        "other_item_code": "I-1",
        "other_item_group": null,
        "other_brand": null,
        "items": [
          {
            "item_code": "I-9",
            "uom": "Nos"
          }
        ],
        "product_discount_slabs": [
          {
            "min_qty": 5.0,
            "max_qty": 0.0,
            "free_item": "I-1",
            "free_qty": 1.0,
            "same_item": 0,
            "free_item_uom": null,
            "free_item_rate": 0.0,
            "warehouse": null,
            "priority": "",
            "disable": 0
          }
        ]
      }
    ],
    "loyalty_point_entries": [
      {
        "as_of_date": "2026-10-22",
        "available_points": 0,
        "company": "nesto",
        "customer": "C-10",
        "earned_points": 164,
        "expired_points": 154,
        "expiry_date": "2026-09-17",
        "invoice": "SI-42",
        "invoice_type": "Sales Invoice",
        "loyalty_points": 157,
        "loyalty_program": "test loyalty",
        "loyalty_program_tier": "Standard",
        "modified": "2026-09-17 11:06:01.107378",
        "name": "LPE-1",
        "posting_date": "2026-09-17",
        "purchase_amount": 3150.0,
        "redeem_against": null,
        "used_points": 10
      },
      {
        "as_of_date": "2026-10-22",
        "available_points": 0,
        "company": "nesto",
        "customer": "C-10",
        "earned_points": 164,
        "expired_points": 154,
        "expiry_date": "2026-09-17",
        "invoice": "SI-43",
        "invoice_type": "Sales Invoice",
        "loyalty_points": -10,
        "loyalty_program": "test loyalty",
        "loyalty_program_tier": "Standard",
        "modified": "2026-09-17 11:07:58.770566",
        "name": "LPE-3",
        "posting_date": "2026-09-17",
        "purchase_amount": 0.0,
        "redeem_against": "LPE-1",
        "used_points": 10
      },
      {
        "as_of_date": "2026-10-22",
        "available_points": 0,
        "company": "nesto",
        "customer": "C-10",
        "earned_points": 164,
        "expired_points": 154,
        "expiry_date": "2026-10-02",
        "invoice": "SI-70",
        "invoice_type": "Sales Invoice",
        "loyalty_points": 7,
        "loyalty_program": "test loyalty",
        "loyalty_program_tier": "Standard",
        "modified": "2026-10-02 11:51:34.633991",
        "name": "LPE-22",
        "posting_date": "2026-10-02",
        "purchase_amount": 150.04,
        "redeem_against": null,
        "used_points": 10
      }
    ],
    "loyalty_snapshot": {
      "as_of_date": "2026-10-22",
      "company": "nesto",
      "mode": "full"
    },
    "voucher_card_batches": [
      {
        "name": "VCB-00008",
        "title": "100 AED Voucher ",
        "company": "nesto",
        "currency": "AED",
        "voucher_amount": 100.0,
        "card_count": 10,
        "valid_from": "2026-10-22",
        "expiry_date": "2026-10-31",
        "use_redemption_hours": 0,
        "active_from_time": null,
        "active_to_time": null,
        "activate_all_cards": 1,
        "generation_status": "Complete",
        "generated_count": 10,
        "all_products": 0,
        "logo": null,
        "terms": "Partial redemption allowed. No cash change. Keep this code secure.",
        "modified": "2026-10-22 16:00:46.286054",
        "restrictions": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ],
        "online_redemption_required": true,
        "use_activation_times": false
      }
    ],
    "gift_voucher_ledger": [
      {
        "name": "7WWJY",
        "creation": "2026-10-22 15:09:07.450777",
        "modified": "2026-10-22 15:18:30.682205",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "7WWJY",
        "barcode": "7WWJY",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10018",
        "issuance_key": "card:VCB-00008:2",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 2,
        "serial_no": 2,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "BUKJ5",
        "creation": "2026-10-22 15:09:07.499523",
        "modified": "2026-10-22 15:18:29.244262",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "BUKJ5",
        "barcode": "BUKJ5",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10022",
        "issuance_key": "card:VCB-00008:6",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 6,
        "serial_no": 6,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "FFK5V",
        "creation": "2026-10-22 15:09:07.510576",
        "modified": "2026-10-22 15:18:30.108976",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "FFK5V",
        "barcode": "FFK5V",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10023",
        "issuance_key": "card:VCB-00008:7",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 7,
        "serial_no": 7,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "GV-63A410BD",
        "creation": "2026-08-22 12:55:46.726229",
        "modified": "2026-08-22 12:55:46.726229",
        "modified_by": "pos.api@arabscale.com",
        "owner": "pos.api@arabscale.com",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "GV-63A410BD",
        "barcode": "GV-63A410BD",
        "status": "Unused",
        "voucher_amount": 50.0,
        "balance_amount": 50.0,
        "issued_date": "2026-08-22",
        "expiry_date": "2026-09-21",
        "promotion": "AED 50 on buying worth 100",
        "issued_against_type": "Sales Invoice",
        "issued_against": "SI-34",
        "customer": "C-7",
        "customer_name": "Book Customer",
        "mobile_no": null,
        "company": "nesto",
        "warehouse": "Stores - N",
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-2",
        "issuance_key": null,
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": null,
        "card_number": 0,
        "serial_no": null,
        "valid_from": null,
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Promotion Voucher",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": "Expired",
        "valid": false,
        "current_status": "Expired",
        "online_redemption_required": true,
        "use_activation_times": false
      },
      {
        "name": "GV-DC3F2413",
        "creation": "2026-08-22 10:54:24.530197",
        "modified": "2026-08-22 12:55:46.734969",
        "modified_by": "pos.api@arabscale.com",
        "owner": "pos.api@arabscale.com",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "GV-DC3F2413",
        "barcode": "GV-DC3F2413",
        "status": "Redeemed",
        "voucher_amount": 50.0,
        "balance_amount": 0.0,
        "issued_date": "2026-08-22",
        "expiry_date": "2026-09-21",
        "promotion": "AED 50 on buying worth 100",
        "issued_against_type": "Sales Invoice",
        "issued_against": "SI-33",
        "customer": "C-7",
        "customer_name": "Book Customer",
        "mobile_no": null,
        "company": "nesto",
        "warehouse": "Stores - N",
        "redeemed_against_type": "Sales Invoice",
        "redeemed_against": "SI-34",
        "redeemed_date": "2026-08-22",
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-1",
        "issuance_key": null,
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": null,
        "card_number": 0,
        "serial_no": null,
        "valid_from": null,
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Promotion Voucher",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": "Redeemed",
        "valid": false,
        "current_status": "Redeemed",
        "online_redemption_required": true,
        "use_activation_times": false
      },
      {
        "name": "J35XM",
        "creation": "2026-10-22 15:09:07.488276",
        "modified": "2026-10-22 15:18:30.401517",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "J35XM",
        "barcode": "J35XM",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10021",
        "issuance_key": "card:VCB-00008:5",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 5,
        "serial_no": 5,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "JVB3H",
        "creation": "2026-10-22 15:09:07.478430",
        "modified": "2026-10-22 15:18:29.531196",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "JVB3H",
        "barcode": "JVB3H",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10020",
        "issuance_key": "card:VCB-00008:4",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 4,
        "serial_no": 4,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "QFCRL",
        "creation": "2026-10-22 15:09:07.313819",
        "modified": "2026-10-22 15:18:28.352190",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "QFCRL",
        "barcode": "QFCRL",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10017",
        "issuance_key": "card:VCB-00008:1",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 1,
        "serial_no": 1,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "RUBXB",
        "creation": "2026-10-22 15:09:07.465324",
        "modified": "2026-10-22 15:18:30.970848",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "RUBXB",
        "barcode": "RUBXB",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10019",
        "issuance_key": "card:VCB-00008:3",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 3,
        "serial_no": 3,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "S5FWT",
        "creation": "2026-10-22 15:09:07.523642",
        "modified": "2026-10-22 15:18:28.652203",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "S5FWT",
        "barcode": "S5FWT",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10024",
        "issuance_key": "card:VCB-00008:8",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 8,
        "serial_no": 8,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "SVBG2",
        "creation": "2026-10-22 15:09:07.534073",
        "modified": "2026-10-22 15:18:28.930347",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "SVBG2",
        "barcode": "SVBG2",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10025",
        "issuance_key": "card:VCB-00008:9",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 9,
        "serial_no": 9,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      },
      {
        "name": "VH9AV",
        "creation": "2026-10-22 15:09:07.545962",
        "modified": "2026-10-22 15:18:29.820211",
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "voucher_code": "VH9AV",
        "barcode": "VH9AV",
        "status": "Unused",
        "voucher_amount": 100.0,
        "balance_amount": 100.0,
        "issued_date": "2026-10-22",
        "expiry_date": "2026-10-31",
        "promotion": null,
        "issued_against_type": null,
        "issued_against": null,
        "customer": null,
        "customer_name": null,
        "mobile_no": null,
        "company": "nesto",
        "warehouse": null,
        "redeemed_against_type": null,
        "redeemed_against": null,
        "redeemed_date": null,
        "notes": null,
        "_user_tags": null,
        "_comments": null,
        "_assign": null,
        "_liked_by": null,
        "custom_document_code": "GVL-10026",
        "issuance_key": "card:VCB-00008:10",
        "currency": "AED",
        "external_pos_reference": null,
        "pos_promotion_reference": null,
        "voucher_card_batch": "VCB-00008",
        "card_number": 10,
        "serial_no": 10,
        "valid_from": "2026-10-22",
        "card_archived": 0,
        "card_blocked": 0,
        "voucher_kind": "Voucher Card",
        "active_from_time": null,
        "active_to_time": null,
        "use_redemption_hours": 0,
        "reason": null,
        "valid": true,
        "current_status": "Active",
        "online_redemption_required": true,
        "use_activation_times": false,
        "all_products": false,
        "eligibility": [
          {
            "idx": 1,
            "item_code": "I-14",
            "item_name": "1foc",
            "barcode": "BC137045713",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "",
            "item_group": "",
            "matching_item_groups": []
          },
          {
            "idx": 2,
            "item_code": "I-20",
            "item_name": "Book",
            "barcode": "book1",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 3,
            "item_code": null,
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": "Celesta Demo",
            "item_group": null,
            "matching_item_groups": []
          },
          {
            "idx": 4,
            "item_code": "",
            "item_name": "",
            "barcode": "",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "brand": null,
            "item_group": "paper",
            "matching_item_groups": [
              "paper"
            ]
          }
        ]
      }
    ],
    "voucher_snapshot": {
      "mode": "full",
      "company": "nesto",
      "warehouse": "Stores - N",
      "as_of": "2026-10-22 17:43:31.429461",
      "server_timezone": "Asia/Dubai",
      "online_redemption_required": true
    }
  }
}
```

Full response: [pos-promotions-local-sample.json](retail/docs/pos-promotions-local-sample.json).
The saved development counter is `Karama / counter01`; `C001` is illustrative.
Examples contain expired offers: apply downloaded validity and status checks.

Each product contains every Promo Price Item field. The parent includes the saved promotion details and Frappe document metadata; internal `linked_schemes` are excluded.

| Form column | JSON field | Meaning |
| --- | --- | --- |
| Item / Category / Brand | `item` / `item_group` / `brand` | Use the target selected by `promotion_scope`; WHOLE BILL has no item target. Resolve names through master data. |
| Cu.SP Ex.VAT / Cu.SP In.VAT | `current_price` / `current_price_including_tax` | Saved selling-price snapshot, using the form's Qty basis. |
| Cu.PP Ex.VAT / Cu.PP In.VAT | `purchase_price` / `purchase_price_including_tax` | Saved purchase reference rates for the selected UOM; not stock valuation or COGS. |
| Discount Amount | `discount_amount` | Amount against Cu.SP In.VAT; counterpart derived when percentage is the input. |
| Discount % | `discount_percent` | Numeric percentage, not a formatted string; show with two decimals in .NET (`F2`). |
| Discount input | `discount_input` | `Amount`, `Percent`, or empty for a fixed price/no discount. Clear the selected input before switching methods. |
| Pro.P Ex.VAT / Pro.P In.VAT preview | `calculated_promo_price` / `calculated_promo_price_including_tax` | Two-decimal preview matching the form; zero is valid for 100% discount. |
| Fixed promo price inputs | `promo_price` / `promo_price_including_tax` | Existing fixed-rate fields, unchanged. They remain zero/empty on discount-based offers. |
| VAT %, Qty, UOM, Barcode, Price List | `vat_rate`, `qty`, `uom`, `barcode`, `price_list` | Saved row values. |
| Max.Qty in One Sale | Product `max_qty` | Row limit; use the parent `max_qty` when the row limit is zero. |

.NET must apply **one promotion method**: when `discount_percent` is nonzero, use that discount rule; do not also subtract `discount_amount` or apply a calculated preview as another discount. When it is zero, retain the existing fixed-price behavior. `discount_input` describes the form input; the percentage is still the existing discount-rule contract for POS clients. Item Group offers use the percentage against each matching item's price; their zero price previews are not fixed item rates.

Calculated previews use the saved selling prices and percentage, rounded to two decimals. Purchase rates are saved snapshots and update when the promotion is saved; changing only the Item does not modify this promotion's incremental-download timestamp. Older percentage offers without `discount_input` return `Percent` and a derived amount. Numeric JSON values may appear as `10.0` rather than `10.00`; formatting belongs in the POS display. Dates retain `yyyy-MM-dd` strings.

After deploying this update, download once **without `modified_after`** to refresh existing cached offers with the additional fields. Then resume incremental downloads. Add the six new product properties to the .NET response model: `purchase_price`, `purchase_price_including_tax`, `discount_amount`, `discount_input`, `calculated_promo_price`, and `calculated_promo_price_including_tax`.

### Download buy/get offers

`GET /api/method/retail.api.pos_sync.get_pos_buy_x_get_y_promotions?branch=Karama&counter_code=C001`

Optional `modified_after`. Keep a separate saved time for each API. Apply the returned dates, scope and disabled flags; do not recalculate saved bills.

Request body: none; use the URL values above.

Response example:

```json
{
  "message": {
    "status": "Success",
    "server_time": "2026-10-14 09:00:00",
    "server_timezone": "Asia/Dubai",
    "branch": "Karama",
    "counter": "Karama-C001",
    "counter_code": "C001",
    "promotions": [
      {
        "name": "Buy 2 Get 1",
        "promotion_version": "0b3fba1fb599019c5097f27c4bf00d74966af6f1d7f0064847a4b92c40a1dae9",
        "description": "Buy 2 Get 1",
        "enabled": 1,
        "disabled": 0,
        "promotion_scope": "ITEM",
        "active_from": null,
        "active_to": null,
        "active_from_time": "09:00:00",
        "active_to_time": "12:00:00",
        "company": "Example Company",
        "warehouse": "Stores - EC",
        "buy_qty": 2,
        "free_qty": 1,
        "same_product_only": 1,
        "priority": "1",
        "modified": "2026-10-14 08:00:00",
        "products": [
          {
            "name": "example-buy-row",
            "idx": 1,
            "add_to": "Buy Item",
            "item": "ITEM-001",
            "item_name": "Example Item",
            "barcode": "ITEM-001-BARCODE",
            "has_serial_no": 0,
            "serial_no": "",
            "serial_numbers": [],
            "item_group": "",
            "brand": "",
            "matching_item_groups": [],
            "uom": "Nos"
          }
        ]
      }
    ]
  }
}
```

Buy Item rows follow `promotion_scope`. Free Item rows always identify a specific
`item`; their `item_group` and `brand` are blank. With `same_product_only: 1`,
the free product is the qualifying purchased Item, including when qualification
uses CATEGORY or BRAND. Quantity and free-quantity calculations are unchanged.

#### Buy one/get one with a different item, category or brand

The existing Buy X Get Y model supports a **qualifying** ITEM, CATEGORY or
BRAND, with a **specific free Item** from any category/brand. Send these rules
in `buy_x_get_y_promotions` on `get_pos_promo_prices`; no change to the old
`promotions` array is required. `same_product_only: 0` selects explicit
`Free Item` rows. With `same_product_only: 1`, the free item must instead be
the qualifying purchased item.

Actual local example: `Buy 2 tea + Get 1 Muffin free` buys `I-27` (Tea,
category `Books`, no Brand) and rewards `I-23` (Chocolate Muffin, category
`Raw Material`, Brand `Emirates`). These are the current saved Item values,
even though the Tea category name is unusual. Do not infer category/brand
from the item description. Resolve reward Item metadata using the normal
Item master download. The actual rule uses buy quantity 2; the following
buy-one/get-one examples are **illustrative configurations, not saved offers**.
Their additional date/version/branch fields follow the real response above.

```json
[
  {
    "description": "Buy one Tea, get one Chocolate Muffin",
    "promotion_scope": "ITEM",
    "buy_qty": 1,
    "free_qty": 1,
    "same_product_only": 0,
    "products": [
      {"add_to": "Buy Item", "item": "I-27", "item_name": "Tea", "barcode": "BC696861983", "has_serial_no": 0, "serial_no": "", "serial_numbers": [], "item_group": "", "brand": "", "matching_item_groups": [], "uom": "Nos"},
      {"add_to": "Free Item", "item": "I-23", "item_name": "Chocolate Muffin", "barcode": "muf123", "has_serial_no": 0, "serial_no": "", "serial_numbers": [], "item_group": "", "brand": "", "matching_item_groups": [], "uom": "Nos"}
    ]
  },
  {
    "description": "Buy one qualifying category item, get one Chocolate Muffin",
    "promotion_scope": "CATEGORY",
    "buy_qty": 1,
    "free_qty": 1,
    "same_product_only": 0,
    "products": [
      {"add_to": "Buy Item", "item": "", "item_name": "", "barcode": "", "has_serial_no": 0, "serial_no": "", "serial_numbers": [], "item_group": "Books", "brand": "", "matching_item_groups": ["Books"], "uom": "Nos"},
      {"add_to": "Free Item", "item": "I-23", "item_name": "Chocolate Muffin", "barcode": "muf123", "has_serial_no": 0, "serial_no": "", "serial_numbers": [], "item_group": "", "brand": "", "matching_item_groups": [], "uom": "Nos"}
    ]
  },
  {
    "description": "Buy one Emirates brand item, get one Tea",
    "promotion_scope": "BRAND",
    "buy_qty": 1,
    "free_qty": 1,
    "same_product_only": 0,
    "products": [
      {"add_to": "Buy Item", "item": "", "item_name": "", "barcode": "", "has_serial_no": 0, "serial_no": "", "serial_numbers": [], "item_group": "", "brand": "Emirates", "matching_item_groups": [], "uom": "Nos"},
      {"add_to": "Free Item", "item": "I-27", "item_name": "Tea", "barcode": "BC696861983", "has_serial_no": 0, "serial_no": "", "serial_numbers": [], "item_group": "", "brand": "", "matching_item_groups": [], "uom": "Nos"}
    ]
  }
]
```

For CATEGORY, always use the downloaded `matching_item_groups` including
descendants; the single-name list above is illustrative. Free Item rows do
not become CATEGORY/BRAND selectors. A reward such as "choose any free item
from Brand B/Category B" is **not supported by this Buy X Get Y setup**;
it needs a separately agreed reward-selection model. Native Pricing Rules
also expose their existing `apply_rule_on_other`, `other_item_code`,
`other_item_group` and `other_brand` fields unchanged; those have native
Pricing Rule semantics and must not be interpreted as Buy X Get Y Free Item rows.

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

Also included in master data. Use a full download; `server_date` is not a changes-since timestamp. The standalone API also accepts `modified_after`; save `server_time` after storing its reply when using incremental downloads.

Request JSON:

```json
{"branch": "Karama", "counter_code": "C001"}
```

Response example:

```json
{
  "message": {
    "server_date": "2026-10-14",
    "server_time": "2026-10-14 09:00:00",
    "server_timezone": "Asia/Dubai",
    "promotions": [
      {
        "name": "Spend 100 Get Voucher",
        "promotion_version": "6bc750fc0ba2fd8c3322596a8b4180660ce64a325f45d18de5147f636635a60c",
        "description": "Spend 100 Get Voucher",
        "enabled": 1,
        "disabled": 0,
        "active_from": "2026-10-14",
        "active_to": "2026-10-31",
        "active_from_time": "18:00:00",
        "active_to_time": "22:00:00",
        "company": "Example Company",
        "warehouse": "Stores - EC",
        "min_sales_value": 100,
        "voucher_amount": 10,
        "multiply_with_sales_amount": 0,
        "expiry_days": 30,
        "modified": "2026-10-14 08:00:00",
        "excluded_item_groups": []
      }
    ]
  }
}
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

### Completed-sale discount repair

Completed receipts retain POS item discounts unchanged. Bill discount is a summary;
ERP does not distribute it again across items. Item VAT helpers use the reported
line VAT. POS Discount Report reads immutable snapshots for older receipts too,
shows the bill summary once, and includes a quantity-adjusted line discount total.
Legacy VAT-exclusive `amount` values remain supported when distinct from the
VAT-inclusive `rate * qty`.

After deploying Retail and building assets, a saved receipt's display can be
previewed and repaired without reposting accounting or stock:

```bash
bench --site <receiving-site> execute retail.pos_completed_sale.repair_discount_display --kwargs '{"invoice_name": "POS-19"}'
bench --site <receiving-site> execute retail.pos_completed_sale.repair_discount_display --kwargs '{"invoice_name": "POS-19", "dry_run": 0}'
```

Unposted accepted transactions are retried by `retail.pos_settlements.recover`.
Keep the original transaction references and payload; never create a replacement
bill to work around a posting exception. Structural/account configuration failures
remain pending with their recorded reason; business-policy discrepancies are audited.

The general mapper uses the item discount key on every calculation, including explicit zero; an
omitted discount defaults to zero rather than a price/VAT difference. Retail form
VAT/discount recalculation also skips completed snapshots. The batch helper
`retail.pos_completed_sale.repair_all_discount_displays` defaults to preview and
is idempotent when applied with `dry_run=0`.

### Promotion usage history (additive; existing endpoints)

All three existing promotion downloads (including master data) now include:

- `enabled`: `1` when the master is enabled, otherwise `0`.
- `disabled`: inverse of `enabled`; existing master flags remain compatible.
- `promotion_version`: opaque version identifier. Store it alongside the cached rule.

The download calls the promotion document ID `name` (the existing field).
When sending a completed sale, copy this **parent** `name` into
`applied_promotions[].promotion`; do not use a product child row's `name`.
Copy the same parent's `promotion_version` into
`applied_promotions[].promotion_version` unchanged:

| Promotion download | Completed-sale request |
|---|---|
| `promotions[].name` | `applied_promotions[].promotion` |
| `promotions[].promotion_version` | `applied_promotions[].promotion_version` |

For example, a downloaded Promo Price with `name: "Chicken offer"` is returned
as `promotion: "Chicken offer"`, with `promotion_type: "Promo Price"`.
See the complete usage payload below. All version strings in examples are
illustrative; clients must copy the actual value returned by ERP.

Disabled, expired and future rules continue to be downloaded. POS replaces cached
rules by ID, honors enabled/disabled, and evaluates date/hour boundaries against
**original sale time in `server_timezone`**, including overnight daily windows.
An offer expiring naturally does not change its modified timestamp; POS must
check its schedule locally on every new sale. Download once without
`modified_after` after this update, then resume existing incremental downloads.

Add optional `applied_promotions` to the existing completed invoice, credit,
return and exchange requests. Send `item_code` to identify each promotional
item. The array belongs at invoice level, alongside `items`, not inside an item.
The following is an excerpt of the existing request; retain the normal `items`,
payments and other required fields. No endpoint or financial field changes:

```json
{
  "posting_date": "2026-10-17",
  "posting_time": "11:30:00",
  "applied_promotions": [
    {
      "promotion_type": "Promo Price",
      "promotion": "Chicken offer",
      "promotion_version": "9aee4b401956750a4a3f31583fa74c0697fa4014e8e159cb17f37cb540571305",
      "item_code": "I-48",
      "quantity": 2,
      "free_quantity": 0,
      "discount_amount": 2,
      "sales_amount": 18
    }
  ]
}
```

ERP matches `item_code` to the invoice's `items` array. Only promotional items
need entries: a bill with 10 item rows and 3 promotional rows sends all 10 rows
in `items` and 3 entries in `applied_promotions`.
If the item code occurs more than once, also send `barcode` and/or `uom` to
identify exactly one row. `item_row` is an optional fallback only when those
fields still match multiple rows, and remains supported for existing clients.
Unmatched or ambiguous entries are retained as Review Required and excluded
from summary amounts; the completed invoice is still accepted. When both
`item_row` and item identity fields are sent, they must agree. Exchange matching
uses the original mixed request before splitting sale and return rows.
Retail also accepts the terminal's `items[].applied_promotions` format. Each
nested entry supplies `promotion_type`, `promotion`, `promotion_version`, and
`promotion_discount_amount`. Retail takes item identity, `qty`, and final
`net_amount` from the parent item. `promotion_discount_amount` is the total
promotion discount for that line, not per unit; it includes VAT when the parent
has `rate_includes_vat: 1`, using its `vat_rate` to convert to exclusive VAT for
reports. For example, a discount of 1 at 5% VAT reports 0.95, with parent
`qty: 1` and `net_amount: 8.57` reporting quantity 1 and net sales 8.57.
An explicit nested `discount_amount` is already exclusive VAT and takes
precedence over the alias. Missing discount evidence stays Review Required;
Retail never infers it from current prices. An explicit invoice-level
`applied_promotions` array takes precedence over nested arrays, including `[]`,
so clients sending both formats cannot double count. Existing `item_row`
clients remain supported. Nested arrays travel with their parent lines when
an exchange is split. The metadata never changes posted invoice amounts.
Existing saved nested evidence is read by promotion reports without saving
submitted invoices. POS Discount Report displays a separate Promotion Discount
(Ex VAT) column; it is not added again to reported financial discounts.

The optional `item_row` is the 1-based position in request `items`; omit it when
the item code (with barcode/UOM if needed) identifies one row. One entry per promotion
and item row; bill-wide offers must allocate their discounts to affected rows
with consistent rounding. `quantity` is in the sold packing/UOM; `free_quantity`
is included within that quantity, not added to it. `discount_amount` is the
promotion-only total for that row (not per-unit), and `sales_amount` is the
attributed final row net amount, both **excluding VAT** in invoice currency.
Manual discounts must not be reported as promotion discounts. Multiple offers
on one row have separate entries; attributed sales overlap across those offers.
For Buy X Get Y, send entries for qualifying and free rows, with free quantities
and actual promotion discount on the free row. Gift voucher issuance/redemption
continues through the existing voucher fields/APIs and Gift Voucher Ledger;
voucher face value must not be included as a current-sale promotion discount.

Send `[]` when the client supports tracking and no promotion was applied. Omit
this property only for legacy clients: reports show those bills as Not Reported,
not proof of zero promotion usage. Save the evidence locally at bill completion;
never reconstruct it from current rules at sync time. Existing duplicate receipt
handling remains in effect. This metadata never applies a second discount.

Returns send promotion entries with `original_item_row` identifying the original
sale payload's item row and the original promotion ID/version. ERP signs returned
quantities and amounts negatively and labels matching references Return Linked.
These are POS-reported reversals, not a new promotion evaluated on return date.
Mixed exchange entries use item codes matched against the original mixed
request (or its positions when the optional `item_row` is supplied); ERP remaps
metadata to the existing split invoices without changing amounts.

ERP stores master revisions from installation onward. Sale schedule checks use
the rule revision effective at payload `posting_date` + `posting_time`, never
arrival time. Disabled-at-sale, stale/missing versions, out-of-window sales,
missing timestamps or pre-install history are Review Required; the completed
sale still posts using existing financial behavior. Historical attribution is
never guessed. A valid old sale arriving after expiry/disable is Schedule Valid
when its original version and original sale time match retained history.

Reports: **Promotions → Promotion History → Promotion Sales Summary / Detail**.
Reports cover submitted Offline POS invoices, exclude cancelled documents, retain
POS invoice links after consolidation, separate currencies, and respect invoice
permissions. Schedule Valid verifies enabled status, company/warehouse and time
window only; item eligibility and discount arithmetic remain POS-reported.
Summary amounts are net of reported returns; receipt counts are distinct per
group. Do not sum attributed sales across promotions because they may overlap.
Unposted/queued transactions are monitored through existing POS sync logs.

### Sales item eligibility in master downloads

`get_pos_master_data` sends only Items with `is_sales_item = 1`, including their packing details, barcodes and selling prices. This applies to full and incremental downloads. After this update, perform a full master download and replace the cached item catalogue (including related packings, barcodes and prices) to remove previously downloaded non-sales items. Incremental omission alone does not remove an existing cached item. Completed bills remain unchanged.

### Item-master scale sales layout

Retail sales forms and the existing `retail.api.scale_item_api.parse_barcode`
endpoint support the prefix-99 master layout described in
`retail/docs/scale_barcode_sales.md`. Exact saved barcodes take precedence.
Dynamic decoding requires a checked Scale Item, an enabled sales Item, and a
7-digit master barcode starting with `99`. Existing download fields `barcode`,
`is_scalable_item` and `scale_barcode_type` identify the master and its selected
type. No new POS sale-sync endpoint or completed-sale recalculation is introduced.

Weight/Quantity labels contain master 7 + value 5 + trailing digit 1 (13 total).
Price contains master 7 + price 5 + trailing digit 1 (13 total). Weight+UPrice
and Weight+TotPrice contain master 7 + weight 5 + price 5 + trailing digit 1
(18 total). Price has two implied decimal places, so `03050` is 30.50.
Weight has three decimals for Kg. The final digit is excluded without checksum
validation. The Item master's selected type determines interpretation.

The existing `scale_barcode_formats` collection describes legacy configured
formats; it is not a replacement for this Item-master layout. External .NET
clients must explicitly adopt the five-digit price layout in their scanner and
configure the scale identically. This Retail implementation does not modify the
.NET executable or reinterpret already completed POS payloads.

### Voucher cards: lookup and redemption

Card details are in `voucher_card_batches` and `gift_voucher_ledger` in the
**Download special prices and other promotions** response above. `voucher_kind`
distinguishes `Voucher Card` from `Promotion Voucher`.

Use `voucher_amount` for original value and `balance_amount` for remaining value.
`status` is stored status; `current_status`, `valid` and `reason` reflect current
activation, expiry, blocking and archive rules. `Unused` with `valid=true` means
an active full-balance card. Inactive rows remain in the snapshot.

`use_activation_times` (legacy alias `use_redemption_hours`) enables one continuous
period from `valid_from` + `active_from_time` through `expiry_date` + `active_to_time`,
in `server_timezone`. These are not daily hours. When disabled, times are null
and full validity dates apply.

Cards are promotional discounts. Approve spending online through the existing
`POST /api/method/retail.api.gift_vouchers.redeem_gift_voucher` before completing
the sale. Downloaded balances do not authorize offline spending.

For batch cards, send `bill_total` before voucher discount; restricted cards also
require `items`. Item amounts must be after other discounts and before the voucher.
Use `amount_including_vat`, or `net_amount` / `amount` as fallback. ERP checks saved
Item/brand/category eligibility, including category descendants; selectors match
with OR. An explicit zero line stays zero. Approval cannot exceed eligible spend
or remaining balance.

```json
{
  "branch": "YOUR-BRANCH",
  "counter_code": "YOUR-COUNTER",
  "voucher_code": "A7K2P",
  "external_pos_reference": "YOUR-UNIQUE-SALE-REFERENCE",
  "redemption_reference": "YOUR-UNIQUE-REDEMPTION-REFERENCE",
  "amount": 10,
  "bill_total": 80,
  "items": [
    {"item_code": "ELIGIBLE-ITEM", "amount_including_vat": 35},
    {"item_code": "OTHER-ITEM", "amount_including_vat": 45}
  ]
}
```

Retry the identical request and references. Successful retries do not debit twice,
even after expiry/blocking. Include the approval in the existing `voucher_redemption`
sale object and apply its amount once as a discount. Invoice sync binds that approval
without another debit; cancellation restores the recorded debit once. Block/archive
flags remain in effect after reversal. Legacy promotion voucher requests are unchanged.

Voucher snapshots are company-scoped; ledger warehouse must match the counter or
be blank. Replace both arrays on every response, including `modified_after` requests.
An empty array clears its cache. No extra transaction-history rows are created by
this download.

## Sales Order app — any client language

These additions use the same ERP and API file. Existing POS requests stay the same.
There are **two new APIs** and an optional new mode on **upsert_customer**.
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
{"message":"Logged In","home_page":"/app","full_name":"Sales Person"}
```

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

```json
{"queries":[{"doctype":"Sales Order","fields":["name","customer","customer_name","transaction_date","delivery_date","grand_total","currency","status","docstatus","modified"],"page_length":1000}]}
```

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

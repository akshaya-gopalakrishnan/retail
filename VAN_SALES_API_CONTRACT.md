# Van Sales API Contract

Prepared: 24 November 2026. Sample IDs and amounts only. Examples are independent calls, not a transaction sequence.

**Status:** Van endpoints are implemented in Retail. Deployment and validation details are recorded at the end of this document.

## Connection

Base URL: `https://<erp-address>`

Send JSON with `Content-Type: application/json` and `Accept: application/json`.
Existing POS calls use `Authorization: token <api_key>:<api_secret>` and require POS access, the POS Integration User role, and an authorized active branch/counter. Driver credentials alone do not grant POS API access.
Van calls use the authenticated driver's ERP session cookie after login. `sessionid` below means the business Van Session, not the authentication cookie. ERP checks driver, company and van access against the logged-in user. Alternatively, use an API token belonging to that assigned Van Sales user.

`organizationid` = ERP Company name; `driverid` = Driver name; `vanid` = Van Fleet name; `customerid` = Customer name. Use the exact downloaded IDs.
GET requests use URL parameters, with no JSON body. Responses below show all returned fields for the illustrated request variant. Arrays contain representative sample records; row counts vary. Full ERP documents include the custom fields installed on `retail-test.localhost`. Native warning/verification metadata can vary by site. Send dates/times in the ERP site timezone (`server_timezone` in the master response); `session_date` is the selected business date.


## One-time setup

The driver needs the existing ERP licensing/seat authorization for password login. These APIs do not change licensing or user-role assignments.

On `retail-test.localhost`, configure Driver → Van Sales Login and give that user Van Sales access/role. Use the actual ERP Driver ID; a Sales Person ID such as `SP-1` is not a Driver ID.

Set an active Van Fleet's default driver, van warehouse, Selling Price List, Cost Center and Loading / Return Warehouse. Company comes from the van warehouse. Sales taxes use the fleet template or company default plus existing item VAT rules. This version supports company-currency price lists and Cash/Bank payment accounts.

A manager assigns a **Draft Van Session** to the driver/login first. `start_session` opens/submits that draft; it does not let a driver create or change their own assignment. Send `sessionid` if multiple drafts exist. Configure Mode of Payment company accounts and Van Expense Type records before posting collections/expenses. Native payment setup requires existing Account Read or Select permission on the payment login. This implementation does not grant it or alter role permissions. A user without that access receives a permission error for collections or paid sales; other authorized calls remain available.

## Unified app login

`POST /api/method/retail.api.auth.login`

Request:
```json
{
  "usr": "driver@example.com",
  "pwd": "<password>"
}
```
Response:
```json
{
  "message": {
    "status": "Success",
    "user": "driver@example.com",
    "app_module": "van_sales",
    "sales_person_id": null,
    "sales_person_name": null,
    "roles": [
      "Van Sales User"
    ],
    "permissions": {
      "sales": false,
      "van_sales": true
    },
    "driverid": "DRV-00001",
    "vanid": "VAN-00001",
    "organizationid": "nesto",
    "sessionid": "VS-2026-00001"
  }
}
```

No active session: `message.sessionid: null`. Native top-level `full_name` and `home_page` may also be present.

Incomplete authentication response:
```json
{
  "message": {
    "status": "AuthenticationRequired",
    "detail": "Complete ERP password reset or two-factor authentication."
  }
}
```

## Master download without branch/counter

`GET /api/method/retail.api.van_sales.get_van_master_data`

No branch or counter is required. With the driver's cookie/token, ERP resolves the company and van warehouse. Optional parameters: `driverid`, `organizationid`, `sessionid`, `vanid`, `warehouse`, `modified_after`. Supplied IDs must match the assignment.

Response:
```json
{
  "message": {
    "bill_format": {
      "address": "Dubai, UAE",
      "email_id": "sales@example.com",
      "f1": "Thank You for Shopping",
      "f2": "Please Visit Again...",
      "f3": "",
      "f4": "",
      "f5": "",
      "h1": "Sample Company",
      "h2": "Dubai, UAE",
      "h3": "",
      "h4": "",
      "h5": "",
      "phone_number": "971500000000",
      "tax_id": "100000000000001"
    },
    "cost_center": "Main - N",
    "currency": "AED",
    "customers": [
      {
        "customer_group": "Business Demo",
        "customer_name": "Sample Customer",
        "email_id": "",
        "mobile_no": "",
        "modified": "2026-11-24 13:37:21.351298",
        "name": "C-1",
        "tax_id": null,
        "territory": "Business Demo"
      }
    ],
    "driverid": "DRV-00001",
    "item_barcodes": [
      {
        "barcode": "VAN-SAMPLE-001",
        "has_serial_no": 0,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "modified": "2026-11-24 13:37:23.188378",
        "serial_no": "",
        "serial_numbers": [],
        "uom": "Nos"
      },
      {
        "barcode": "2000000000084",
        "has_serial_no": 0,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "modified": "2026-11-24 13:37:23.187971",
        "serial_no": "",
        "serial_numbers": [],
        "uom": "Nos"
      }
    ],
    "item_prices": [
      {
        "barcode": "2000000000084",
        "currency": "AED",
        "has_serial_no": 0,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "modified": "2026-11-24 13:37:23.349985",
        "name": "32150olhfg",
        "price_list": "Standard Selling",
        "price_list_rate": 10.5,
        "rate_includes_vat": 1,
        "serial_no": "",
        "serial_numbers": [],
        "uom": "Nos"
      }
    ],
    "items": [
      {
        "actual_qty": 6.0,
        "arabic_item_name": null,
        "barcode": "2000000000084",
        "batches": [],
        "brand": null,
        "created_by": "Administrator",
        "created_on": "2026-11-24 13:37:16.757524",
        "current_stock": 6.0,
        "disabled": 0,
        "has_batch_no": 0,
        "has_serial_no": 0,
        "is_fast_plu_item": 0,
        "is_open_price": 0,
        "is_scalable_item": 0,
        "is_stock_item": 1,
        "is_taxable": 1,
        "item_code": "I-1",
        "item_group": "KG",
        "item_name": "Sample Item",
        "item_tax_template": "UAE VAT 5% - N",
        "modified": "2026-11-24 13:37:23.120706",
        "modified_by": "Administrator",
        "modified_on": "2026-11-24 13:37:23.120706",
        "name": "I-1",
        "packings": [
          {
            "actual_qty": 6.0,
            "arabic_packing_name": "",
            "barcode": "VAN-SAMPLE-001",
            "barcode_type": "",
            "conversion_factor": 1.0,
            "current_stock": 6.0,
            "disabled": 0,
            "has_serial_no": 0,
            "idx": 1,
            "is_fast_plu_item": 0,
            "is_taxable": 1,
            "item_code": "I-1",
            "item_name": "Sample Item",
            "item_tax_template": "UAE VAT 5% - N",
            "modified": "2026-11-24 13:37:23.120706",
            "name": "31vfri8m3p",
            "packing_code": "I-1-NOS",
            "packing_group": "KG",
            "packing_margin": 2.5,
            "packing_name": "Each",
            "purchase_gross_rate": 8.4,
            "purchase_net_rate": 8.0,
            "purchase_rate": 8.0,
            "purchase_vat_amount": 0.4,
            "purchase_vat_rate": "5%",
            "purchase_vat_template": "UAE VAT 5% - N",
            "rate_includes_vat": 1,
            "sales_vat_rate": "5%",
            "sales_vat_template": "UAE VAT 5% - N",
            "selling_gross_rate": 11.02,
            "selling_net_rate": 10.5,
            "selling_rate": 11.02,
            "selling_vat_amount": 0.52,
            "serial_no": "",
            "serial_numbers": [],
            "stock_modified": "2026-11-24 13:37:23.071341",
            "tax_rate": 5.0,
            "uom": "Nos"
          }
        ],
        "projected_qty": 6.0,
        "purchase_vat_rate": "5%",
        "purchase_vat_template": "UAE VAT 5% - N",
        "rate_includes_vat": 1,
        "reserved_qty": 0.0,
        "sales_item_tax_template": "UAE VAT 5% - N",
        "sales_rate_includes_vat": 1,
        "sales_vat_rate": "5%",
        "sales_vat_template": "UAE VAT 5% - N",
        "scale_barcode_type": null,
        "selling_gross_rate": 10.5,
        "selling_rate": 10.5,
        "serial_no": "",
        "serial_numbers": [],
        "stock_modified": "2026-11-24 13:37:23.071341",
        "stock_uom": "Nos",
        "stock_value": 48.0,
        "tax_rate": 5.0
      }
    ],
    "modes_of_payment": [
      {
        "name": "Cash"
      }
    ],
    "organizationid": "nesto",
    "packing_details": [
      {
        "actual_qty": 6.0,
        "arabic_packing_name": "",
        "barcode": "VAN-SAMPLE-001",
        "barcode_type": "",
        "conversion_factor": 1.0,
        "current_stock": 6.0,
        "disabled": 0,
        "has_serial_no": 0,
        "idx": 1,
        "is_fast_plu_item": 0,
        "is_taxable": 1,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "item_tax_template": "UAE VAT 5% - N",
        "modified": "2026-11-24 13:37:23.120706",
        "name": "31vfri8m3p",
        "packing_code": "I-1-NOS",
        "packing_group": "KG",
        "packing_margin": 2.5,
        "packing_name": "Each",
        "purchase_gross_rate": 8.4,
        "purchase_net_rate": 8.0,
        "purchase_rate": 8.0,
        "purchase_vat_amount": 0.4,
        "purchase_vat_rate": "5%",
        "purchase_vat_template": "UAE VAT 5% - N",
        "rate_includes_vat": 1,
        "sales_vat_rate": "5%",
        "sales_vat_template": "UAE VAT 5% - N",
        "selling_gross_rate": 11.02,
        "selling_net_rate": 10.5,
        "selling_rate": 11.02,
        "selling_vat_amount": 0.52,
        "serial_no": "",
        "serial_numbers": [],
        "stock_modified": "2026-11-24 13:37:23.071341",
        "tax_rate": 5.0,
        "uom": "Nos"
      }
    ],
    "scale_barcode_formats": [
      {
        "check_digit_enabled": 1,
        "check_digit_method": "EAN13",
        "decimal_places": 3,
        "format_name": "Prefix 99 - 2-5-5",
        "modified": "2026-07-25 13:01:22.685255",
        "name": "Prefix 99 - 2-5-5",
        "plu_length": 5,
        "plu_start": 3,
        "prefix": "99",
        "prefix_length": 2,
        "prefix_start": 1,
        "total_length": 13,
        "value_length": 5,
        "value_start": 8,
        "value_type": "WEIGHT"
      }
    ],
    "selling_price_list": "Standard Selling",
    "server_time": "2026-11-24 13:37:23.382827",
    "server_timezone": "Asia/Dubai",
    "sessionid": "VS-2026-00001",
    "status": "Success",
    "taxes_and_charges": null,
    "vanid": "VAN-00001",
    "warehouse": "Van 01 - N"
  }
}
```

The item/packing/barcode/price/scale payload uses the shared POS catalog builder with the **van warehouse**. Prices are restricted to the configured selling price list. Customers are a full assigned-driver snapshot even when `modified_after` is sent; reconcile local customer access after each successful download. Stock can change independently of Item modification, so do a full master refresh to refresh every item's stock. Promotion, loyalty and voucher downloads continue through their existing POS APIs and authorization; this van endpoint does not add those sections.

## Compatibility with the app's current calls

These routes accept both GET and POST:

| Existing app route suffix under `/api/method/retail.api.pos_sync.` | Van endpoint used internally |
| --- | --- |
| `get_sales_invoices` | `get_sales_invoice_data` |
| `get_sales_returns` | `get_sales_return_data` |
| `get_customer_payments` | `get_customer_payment_data` |
| `get_expenses` | `get_expense_data` |
| `get_active_session` | `get_active_session` |
| `get_van_master_data` | `get_van_master_data` |
| `get_load_stock` | `get_load_stock` |
| `get_credit_customers` | `get_credit_customers` |

POST compatibility routes also exist for `driver_login`, `start_session`, `update_session_status`, `end_session`, `confirm_load`, `unload_stock`, `post_sale`, `post_sales_return`, `post_customer_payment`, `post_expense` and `upsert_van_customer`.

The payload aliases `driver_id`, `session_id`, `van_id`, `organization_id`, `customer_id`, `request_id` and `invoice_id` are accepted. An empty `session_id` resolves the driver's current open session. Posting still requires `requestid`; authentication and actual Driver/warehouse IDs must be correct.

The original POS `get_pos_master_data` and `upsert_customer` routes retain their POS behavior. Use `get_van_master_data` and `upsert_van_customer` on that namespace for the driver-scoped versions.

## Existing POS APIs to reuse

Continue using the existing [POS API contract](POS_API_CONTRACT.md) for master data, items, packing, barcodes, prices, promotions, loyalty, vouchers and existing POS functions. No changes to those payloads are proposed here.

### Master data — available

`GET /api/method/retail.api.pos_sync.get_pos_master_data?branch=Karama&counter_code=C001`

Optional incremental parameter: `modified_after=2026-11-24%2008:00:00`.
`organizationid` alone is not accepted by this existing endpoint. Company and warehouse come from the configured counter; this is not a van warehouse stock download.

Response:
```json
{
  "message": {
    "bill_format": {
      "address": "Dubai, UAE",
      "email_id": "sales@example.com",
      "f1": "Thank You for Shopping",
      "f2": "Please Visit Again...",
      "f3": "",
      "f4": "",
      "f5": "",
      "h1": "Sample Company",
      "h2": "Dubai, UAE",
      "h3": "",
      "h4": "",
      "h5": "",
      "phone_number": "971500000000",
      "tax_id": "100000000000001"
    },
    "buy_x_get_y_promotions": [
      {
        "active_from": "2026-08-21",
        "active_from_time": "08:50:31",
        "active_to": "2026-08-22",
        "active_to_time": "15:50:34",
        "buy_qty": 2.0,
        "company": "nesto",
        "creation": "2026-08-21 17:55:18.426339",
        "custom_document_code": "BXG-1",
        "description": "Buy 2 tea + Get 1 Muffin free",
        "disabled": 0,
        "docstatus": 0,
        "doctype": "Buy X Get Y Promotion",
        "enabled": 1,
        "free_qty": 1.0,
        "idx": 0,
        "modified": "2026-10-15 09:10:12.067501",
        "modified_by": "Administrator",
        "name": "Buy 2 tea + Get 1 Muffin free",
        "notes": null,
        "owner": "pos.api@arabscale.com",
        "priority": "10",
        "products": [
          {
            "add_to": "Buy Item",
            "barcode": "BC696861983",
            "brand": null,
            "group_no": 1,
            "has_serial_no": 0,
            "idx": 1,
            "item": "I-27",
            "item_group": "",
            "item_name": "Tea",
            "matching_item_groups": [],
            "name": "tu06gjrj6f",
            "qty": 0.0,
            "serial_no": "",
            "serial_numbers": [],
            "uom": "Nos"
          },
          {
            "add_to": "Free Item",
            "barcode": "muf123",
            "brand": null,
            "group_no": 1,
            "has_serial_no": 0,
            "idx": 2,
            "item": "I-23",
            "item_group": "",
            "item_name": "Chocolate Muffin",
            "matching_item_groups": [],
            "name": "tu06osv12r",
            "qty": 0.0,
            "serial_no": "",
            "serial_numbers": [],
            "uom": "Nos"
          }
        ],
        "promotion_scope": "ITEM",
        "promotion_version": "3ef692236041a0618b77cd14fffeaf11735dfbb0cdf15966efe5aef1b1a73eb4",
        "same_product_only": 0,
        "warehouse": "Stores - N"
      }
    ],
    "counter": {
      "allow_offline_sync": 1,
      "branch": "Business Demo Branch",
      "card_account": "Banks Current Accounts - N",
      "cash_account": "Main Safe - Foreign Currency - N",
      "company": "nesto",
      "cost_center": "Main - N",
      "counter_code": "counter02",
      "counter_name": "Counter 02",
      "creation": "2026-06-18 16:55:58.386433",
      "custom_document_code": "PC-2",
      "default_customer": "C-4",
      "docstatus": 0,
      "doctype": "POS Branch Counter",
      "idx": 4,
      "integration_user": null,
      "is_active": 1,
      "last_sync_at": null,
      "modified": "2026-11-02 17:12:34.040817",
      "modified_by": "Administrator",
      "name": "Retail Demo Branch-COUNTER-1",
      "owner": "Administrator",
      "pos_profile": "Business Demo POS Profile",
      "printer_name": null,
      "terminal_id": "T02",
      "warehouse": "Stores - N"
    },
    "counters": [
      {
        "branch": "Business Demo Branch",
        "cost_center": "Main - N",
        "counter_code": "counter02",
        "counter_name": "Counter 02",
        "name": "Retail Demo Branch-COUNTER-1",
        "pos_profile": "Business Demo POS Profile",
        "printer_name": null,
        "terminal_id": "T02",
        "warehouse": "Stores - N"
      }
    ],
    "customers": [
      {
        "available_credit": 0,
        "bypass_credit_limit_check": 0,
        "credit_limit": 0.0,
        "credit_note_currency": "AED",
        "credit_notes_applied": 0.0,
        "credit_notes_as_of": "2026-11-24 13:37:23.740343",
        "credit_notes_issued": 0.0,
        "credit_notes_redeemed": 0.0,
        "credit_notes_unresolved": 0.0,
        "credit_sales": 0.0,
        "current_receivable": 0.0,
        "custom_sales_person": null,
        "customer_group": "Business Demo",
        "customer_name": "Sample Customer",
        "gift_vouchers": [],
        "is_credit_customer": 0,
        "loyalty_balances": [
          {
            "as_of_date": "2026-11-24",
            "available_points": 4,
            "conversion_factor": 1.0,
            "currency": "AED",
            "earned_points": 4,
            "expired_points": 0,
            "loyalty_program": "test loyalty",
            "redeemable_amount": 4.0,
            "used_points": 0
          }
        ],
        "loyalty_conversion_factor": 1.0,
        "loyalty_point_entries": [
          {
            "company": "nesto",
            "customer": "C-1",
            "expiry_date": "2026-11-24",
            "invoice": "SINV-2026-00001",
            "invoice_type": "Sales Invoice",
            "loyalty_points": 4,
            "loyalty_program": "test loyalty",
            "loyalty_program_tier": "Standard",
            "modified": "2026-11-24 13:37:21.344568",
            "name": "LPE-55",
            "posting_date": "2026-11-24",
            "purchase_amount": 94.5,
            "redeem_against": null
          }
        ],
        "loyalty_program": "test loyalty",
        "loyalty_program_name": "test loyalty",
        "loyalty_program_tier": "Standard",
        "modified": "2026-11-24 13:37:21.351298",
        "name": "C-1",
        "original_debt_reduction": 0.0,
        "pending_credit_allocations": 0.0,
        "promotions_as_of": "2026-11-24",
        "sales_person_id": null,
        "sales_person_name": null,
        "territory": "Business Demo",
        "unresolved_settlement_amount": 0.0,
        "unused_credit_note_amount": 0.0,
        "unused_credit_notes": []
      }
    ],
    "gift_voucher_promotions": [
      {
        "active_from": "2026-08-22",
        "active_from_time": null,
        "active_to": "2026-08-23",
        "active_to_time": null,
        "company": "nesto",
        "creation": "2026-08-22 09:32:07.577467",
        "custom_document_code": "GVP-1",
        "description": "AED 50 on buying worth 100",
        "disabled": 0,
        "docstatus": 0,
        "doctype": "Gift Voucher Promotion",
        "enabled": 1,
        "excluded_item_groups": [
          {
            "creation": "2026-08-22 09:32:07.577467",
            "docstatus": 0,
            "doctype": "Promotion Excluded Item Group",
            "idx": 1,
            "item_group": "sugary drinks",
            "matching_item_groups": [
              "sugary drinks"
            ],
            "modified": "2026-08-22 10:52:16.118598",
            "modified_by": "pos.api@arabscale.com",
            "name": "2rc8ngn8km",
            "owner": "pos.api@arabscale.com",
            "parent": "AED 50 on buying worth 100",
            "parentfield": "excluded_item_groups",
            "parenttype": "Gift Voucher Promotion"
          }
        ],
        "expiry_days": 30,
        "idx": 0,
        "min_sales_value": 100.0,
        "modified": "2026-08-22 10:52:16.118598",
        "modified_by": "pos.api@arabscale.com",
        "multiply_with_sales_amount": 0,
        "name": "AED 50 on buying worth 100",
        "notes": null,
        "owner": "pos.api@arabscale.com",
        "promotion_version": "04d3556e19b790e7d247f7d4385dbcd709d4a235e98ee22607ba4d317d37a59e",
        "voucher_amount": 50.0,
        "warehouse": "Stores - N"
      }
    ],
    "item_barcodes": [
      {
        "barcode": "VAN-SAMPLE-001",
        "has_serial_no": 0,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "modified": "2026-11-24 13:37:23.188378",
        "serial_no": "",
        "serial_numbers": [],
        "uom": "Nos"
      },
      {
        "barcode": "2000000000084",
        "has_serial_no": 0,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "modified": "2026-11-24 13:37:23.187971",
        "serial_no": "",
        "serial_numbers": [],
        "uom": "Nos"
      }
    ],
    "item_prices": [
      {
        "barcode": "VAN-SAMPLE-001",
        "currency": "AED",
        "has_serial_no": 0,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "modified": "2026-11-24 13:37:23.275223",
        "name": "be13df834d",
        "price_list": "Standard Selling",
        "price_list_rate": 10.5,
        "rate_includes_vat": 1,
        "serial_no": "",
        "serial_numbers": [],
        "uom": "Nos"
      },
      {
        "barcode": "VAN-SAMPLE-001",
        "currency": "AED",
        "has_serial_no": 0,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "modified": "2026-11-24 13:37:23.277629",
        "name": "227d61f555",
        "price_list": "Standard Buying",
        "price_list_rate": 8.0,
        "serial_no": "",
        "serial_numbers": [],
        "uom": "Nos"
      },
      {
        "barcode": "2000000000084",
        "currency": "AED",
        "has_serial_no": 0,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "modified": "2026-11-24 13:37:23.349985",
        "name": "32150olhfg",
        "price_list": "Standard Selling",
        "price_list_rate": 10.5,
        "rate_includes_vat": 1,
        "serial_no": "",
        "serial_numbers": [],
        "uom": "Nos"
      }
    ],
    "items": [
      {
        "actual_qty": 0.0,
        "arabic_item_name": null,
        "barcode": "2000000000084",
        "batches": [],
        "brand": null,
        "created_by": "Administrator",
        "created_on": "2026-11-24 13:37:16.757524",
        "current_stock": 0.0,
        "disabled": 0,
        "has_batch_no": 0,
        "has_serial_no": 0,
        "is_fast_plu_item": 0,
        "is_open_price": 0,
        "is_scalable_item": 0,
        "is_stock_item": 1,
        "is_taxable": 1,
        "item_code": "I-1",
        "item_group": "KG",
        "item_name": "Sample Item",
        "item_tax_template": "UAE VAT 5% - N",
        "modified": "2026-11-24 13:37:23.120706",
        "modified_by": "Administrator",
        "modified_on": "2026-11-24 13:37:23.120706",
        "name": "I-1",
        "packings": [
          {
            "actual_qty": 0.0,
            "arabic_packing_name": "",
            "barcode": "VAN-SAMPLE-001",
            "barcode_type": "",
            "conversion_factor": 1.0,
            "current_stock": 0.0,
            "disabled": 0,
            "has_serial_no": 0,
            "idx": 1,
            "is_fast_plu_item": 0,
            "is_taxable": 1,
            "item_code": "I-1",
            "item_name": "Sample Item",
            "item_tax_template": "UAE VAT 5% - N",
            "modified": "2026-11-24 13:37:23.120706",
            "name": "31vfri8m3p",
            "packing_code": "I-1-NOS",
            "packing_group": "KG",
            "packing_margin": 2.5,
            "packing_name": "Each",
            "purchase_gross_rate": 8.4,
            "purchase_net_rate": 8.0,
            "purchase_rate": 8.0,
            "purchase_vat_amount": 0.4,
            "purchase_vat_rate": "5%",
            "purchase_vat_template": "UAE VAT 5% - N",
            "rate_includes_vat": 1,
            "sales_vat_rate": "5%",
            "sales_vat_template": "UAE VAT 5% - N",
            "selling_gross_rate": 11.02,
            "selling_net_rate": 10.5,
            "selling_rate": 11.02,
            "selling_vat_amount": 0.52,
            "serial_no": "",
            "serial_numbers": [],
            "stock_modified": null,
            "tax_rate": 5.0,
            "uom": "Nos"
          }
        ],
        "projected_qty": 0.0,
        "purchase_vat_rate": "5%",
        "purchase_vat_template": "UAE VAT 5% - N",
        "rate_includes_vat": 1,
        "reserved_qty": 0.0,
        "sales_item_tax_template": "UAE VAT 5% - N",
        "sales_rate_includes_vat": 1,
        "sales_vat_rate": "5%",
        "sales_vat_template": "UAE VAT 5% - N",
        "scale_barcode_type": null,
        "selling_gross_rate": 10.5,
        "selling_rate": 10.5,
        "serial_no": "",
        "serial_numbers": [],
        "stock_modified": null,
        "stock_uom": "Nos",
        "stock_value": 0.0,
        "tax_rate": 5.0
      }
    ],
    "modes_of_payment": [
      {
        "enabled": 1,
        "modified": "2026-11-24 13:37:17.217031",
        "name": "Cash",
        "type": "Cash"
      }
    ],
    "operators": [
      {
        "branch": null,
        "cell_number": null,
        "company": "nesto",
        "designation": "Delivery Person",
        "disabled": 0,
        "employee": "E-7",
        "employee_name": "SAMPLE-001",
        "employee_number": null,
        "login_id": 107,
        "modified": "2026-11-24 12:50:24.618359",
        "name": "E-7",
        "pos_login_enabled": 1,
        "pos_login_id": 107,
        "pos_operator_privilege": "pos cashier",
        "privilege_profile": "pos cashier",
        "privileges": {
          "ADJUSTMENT": true,
          "ADJUST_DAY_CLOSING_PAYMENTS": false,
          "CANCEL_BILL": true,
          "CASHIN_CASHOUT": true,
          "CHANGE_BILL_SETTLEMENT": false,
          "CHANGE_DELIVERYBY": true,
          "CHANGE_PRICE": true,
          "CHANGE_QTY": true,
          "CHANGE_SALESMAN": true,
          "CHANGE_SETTLED_BILL_MOP": false,
          "CHANGE_WAITER": true,
          "CLOCKIN_CLOCKOUT": true,
          "COST_VIEW": true,
          "COUPON": true,
          "CREDIT_CUSTOMER": true,
          "CREDIT_CUSTOMER_LIMIT": true,
          "CREDIT_CUSTOMER_PAYMENT": true,
          "CREDIT_NOTE_ISSUE": true,
          "CREDIT_NOTE_RECALL": true,
          "DAY_CLOSING": true,
          "DELETE_CUSTOMER": false,
          "DISCOUNT_BILL": true,
          "DISCOUNT_ITEM": true,
          "HOLD_BILL": true,
          "INVOICE_LOOKUP": true,
          "INVRECALL_BILL": true,
          "ITEMS_EXCHANGE": true,
          "LOYALTY": true,
          "OPEN_DRAWER": true,
          "PRICE_ENQUIRY": true,
          "PRINT_SHIFT_CLOSING": true,
          "PRODUCT_INFO": true,
          "RECALL_BILL": true,
          "REDEEM": true,
          "REFUND_BILL": true,
          "REOPEN_DAY_CLOSING": false,
          "SALES_REPORT": true,
          "SEND_EMAIL": true,
          "SHIFT_CLOSING": true,
          "VOID_ITEMS": true,
          "WARRANTY_LOOKUP": true
        },
        "quick_pin_hash": "<sample quick_pin_hash>",
        "quick_pin_salt": "<sample quick_pin_salt>",
        "status": "Active",
        "user_id": "sample@example.com"
      }
    ],
    "packing_details": [
      {
        "actual_qty": 0.0,
        "arabic_packing_name": "",
        "barcode": "VAN-SAMPLE-001",
        "barcode_type": "",
        "conversion_factor": 1.0,
        "current_stock": 0.0,
        "disabled": 0,
        "has_serial_no": 0,
        "idx": 1,
        "is_fast_plu_item": 0,
        "is_taxable": 1,
        "item_code": "I-1",
        "item_name": "Sample Item",
        "item_tax_template": "UAE VAT 5% - N",
        "modified": "2026-11-24 13:37:23.120706",
        "name": "31vfri8m3p",
        "packing_code": "I-1-NOS",
        "packing_group": "KG",
        "packing_margin": 2.5,
        "packing_name": "Each",
        "purchase_gross_rate": 8.4,
        "purchase_net_rate": 8.0,
        "purchase_rate": 8.0,
        "purchase_vat_amount": 0.4,
        "purchase_vat_rate": "5%",
        "purchase_vat_template": "UAE VAT 5% - N",
        "rate_includes_vat": 1,
        "sales_vat_rate": "5%",
        "sales_vat_template": "UAE VAT 5% - N",
        "selling_gross_rate": 11.02,
        "selling_net_rate": 10.5,
        "selling_rate": 11.02,
        "selling_vat_amount": 0.52,
        "serial_no": "",
        "serial_numbers": [],
        "stock_modified": null,
        "tax_rate": 5.0,
        "uom": "Nos"
      }
    ],
    "promo_prices": [
      {
        "active_from": "2026-10-20",
        "active_from_time": "00:00:00",
        "active_to": "2028-10-31",
        "active_to_time": "23:59:59",
        "company": "nesto",
        "creation": "2026-10-20 12:47:02.716002",
        "custom_document_code": "PP4-8",
        "description": "promo to whole bill",
        "disabled": 0,
        "docstatus": 0,
        "doctype": "Promo Price",
        "enabled": 1,
        "idx": 0,
        "max_qty": 0.0,
        "min_qty": 0.0,
        "min_sales_value": 100.0,
        "modified": "2026-11-18 15:58:22.419496",
        "modified_by": "Administrator",
        "name": "promo to whole bill",
        "notes": null,
        "owner": "Administrator",
        "priority": "4",
        "products": [
          {
            "barcode": "",
            "brand": "",
            "calculated_promo_price": 0.0,
            "calculated_promo_price_including_tax": 0.0,
            "current_price": 0.0,
            "current_price_including_tax": 0.0,
            "discount_amount": 0.0,
            "discount_input": "Percent",
            "discount_percent": 50.0,
            "has_serial_no": 0,
            "idx": 1,
            "item": "",
            "item_group": "",
            "item_name": "",
            "matching_item_groups": [],
            "max_qty": 0.0,
            "name": "aa3obo84vl",
            "price_list": "",
            "promo_price": 0.0,
            "promo_price_including_tax": 0.0,
            "purchase_price": 0.0,
            "purchase_price_including_tax": 0.0,
            "qty": 0.0,
            "serial_no": "",
            "serial_numbers": [],
            "uom": "",
            "vat_rate": 0.0
          }
        ],
        "promotion_scope": "WHOLE BILL",
        "promotion_version": "35ecbb3e6baac826589cdf2b8a73480ae1c9aed2fb47a5091949257167bb545d",
        "scan_barcode": null,
        "warehouse": null
      }
    ],
    "scale_barcode_formats": [
      {
        "check_digit_enabled": 1,
        "check_digit_method": "EAN13",
        "decimal_places": 3,
        "format_name": "Prefix 99 - 2-5-5",
        "modified": "2026-07-25 13:01:22.685255",
        "name": "Prefix 99 - 2-5-5",
        "plu_length": 5,
        "plu_start": 3,
        "prefix": "99",
        "prefix_length": 2,
        "prefix_start": 1,
        "total_length": 13,
        "value_length": 5,
        "value_start": 8,
        "value_type": "WEIGHT"
      }
    ],
    "server_time": "2026-11-24 13:37:23.686214",
    "server_timezone": "Asia/Dubai",
    "status": "Success",
    "tax_config": {
      "tax_template": "UAE VAT Exempted - N",
      "taxes": [
        {
          "charge_type": "On Net Total",
          "idx": 1,
          "included_in_print_rate": 0,
          "rate": 0.0
        }
      ]
    }
  }
}
```

### Customer create/update — available

`POST /api/method/retail.api.pos_sync.upsert_customer`

Request:
```json
{
  "external_customer_id": "VAN01-CUST-001",
  "branch": "Karama",
  "counter_code": "C001",
  "customer_name": "Sample Customer",
  "customer_group": "All Customer Groups",
  "territory": "All Territories",
  "mobile_no": "971500000000",
  "email_id": "customer@example.com",
  "tax_id": ""
}
```
Response:
```json
{
  "message": {
    "action": "Created",
    "customer": "C-2",
    "status": "Success"
  }
}
```
Reuse the same `external_customer_id` to update; response action becomes `Updated`. This API does not assign a customer to a driver. For driver assignment, use the implemented van customer API below.

### Customer balances — available

`GET /api/method/retail.api.pos_sync.get_customer_balances?company=nesto&customer=C-1&include_zero_balance=0`

Response:
```json
{
  "message": {
    "company": "nesto",
    "count": 1,
    "data": [
      {
        "address": null,
        "address_id": null,
        "available_credit": 0,
        "credit_note_currency": "AED",
        "credit_notes_applied": 0.0,
        "credit_notes_as_of": "2026-11-24 13:37:23.972152",
        "credit_notes_issued": 0.0,
        "credit_notes_redeemed": 0.0,
        "credit_notes_unresolved": 0.0,
        "credit_sales": 0.0,
        "current_balance": 0.0,
        "current_receivable": 0.0,
        "customer": "C-1",
        "customer_name": "Sample Customer",
        "email": "",
        "opening_balance": 0.0,
        "original_debt_reduction": 0.0,
        "payment_amount": 94.5,
        "pending_credit_allocations": 0.0,
        "phone": "",
        "transaction_amount": 105.0,
        "unresolved_settlement_amount": 0.0,
        "unused_credit_note_amount": 0.0,
        "unused_credit_notes": []
      }
    ],
    "from_date": "2026-11-24",
    "status": "Success",
    "to_date": "2026-11-24"
  }
}
```
This existing API does not accept `driverid` or restrict the result to a driver's assigned customers. Use the driver-scoped endpoint below for that requirement.

### Current van stock — available

`GET /api/method/retail.van_stock.get_van_warehouse_stock?warehouse=Van%2001%20-%20N`

Response:
```json
{
  "message": [
    {
      "actual_qty": 6.0,
      "item_code": "I-1",
      "item_name": "Sample Item",
      "stock_uom": "Nos",
      "valuation_rate": 8.0,
      "warehouse": "Van 01 - N"
    }
  ]
}
```
Returns positive stock only. Requires van stock permissions; van operators can read only a warehouse assigned to their open session. This does not list pending loads.

## Van APIs

All URLs in this section start with `/api/method/retail.api.van_sales.` followed by the method name shown. POST samples are request bodies; GET samples are URL query parameters.

For posting APIs, save a unique `requestid` (maximum 140 characters) per action and reuse it on retries. ERP returns the original result with `duplicate: true` on an identical retry; reusing that ID with different data is rejected. `action` is `draft` or `submit`; drafts return `docstatus: 0`, submitted documents return `docstatus: 1`.

Common optional assignment keys: `driverid`, `sessionid`, `vanid`, `organizationid`, `warehouse`. Supplied values must match the assignment. Login uses its own credential keys and requires no `requestid`.

| Request | Additional optional keys |
| --- | --- |
| `get_van_master_data` | `modified_after` |
| `upsert_customer` | `customerid`, `email_id`, `tax_id` (`external_customer_id` required, maximum 140 characters) |
| `confirm_load` | `items[].request_itemid`, `items[].batch_no`, `items[].serial_no` |
| `unload_stock` | `posting_date`, `target_warehouse`, `items[].barcode`, `items[].batch_no`, `items[].serial_no` |
| `start_session` | `sessionid`, `session_date`, `timing`, `opening_balance` (default `0`), `opening_km` |
| `update_session_status` | `timing` |
| `end_session` | `timing`, `closing_km`, `collection_details` (default `[]`), `remarks` |
| `get_sales_invoice_data` | `invoiceid` |
| `post_sale` | `invoiceid`, `posting_date`, `posting_time`, `selling_price_list`, `taxes_and_charges`, `remarks`, `payments` (default `[]`), `action` (default `submit`), `apply_discount_on`, `additional_discount_percentage`, `discount_amount` |
| `post_sale.items[]` | `uom`, `rate`, `discount_percentage`, `discount_amount`, `barcode`, `batch_no`, `serial_no`, `rate_includes_vat` (default `0`) |
| `get_sales_return_data` | `invoiceid`, `returnid` |
| `post_sales_return` | `returnid`, `posting_date`, `action` (default `submit`) |
| `post_sales_return.items[]` | `uom`, `batch_no`, `serial_no`; prices and discounts come from the original invoice |
| `get_customer_payment_data` | `customerid` |
| `post_customer_payment` | `posting_date`, `remarks`, `payment_type` (`Receive` default, or `Pay`) |
| `post_expense` | `posting_date`, `proof_url`, `remarks` |

### 1. Driver login

`POST /api/method/retail.api.van_sales.driver_login`

Request:
```json
{
  "userid": "driver@example.com",
  "password": "<password>"
}
```
Response:
```json
{
  "full_name": "Sample Driver",
  "home_page": "/app/business-home",
  "message": {
    "driverid": "DRV-00001",
    "organizationid": "nesto",
    "sessionid": "VS-2026-00001",
    "status": "Success",
    "vanid": "VAN-00001"
  },
  "permissions": {
    "sales": false,
    "van_sales": true
  },
  "roles": [
    "Accounts User",
    "All",
    "Desk User",
    "Guest",
    "Van Sales User"
  ],
  "sales_person_id": null,
  "sales_person_name": null
}
```
Return `sessionid: null` if no active Van Session exists. ERP resolves the driver/user and van assignment. Normal ERP password restrictions and two-factor authentication still apply; a pending challenge returns `status: "AuthenticationRequired"`.

Native `sales_person_id` / `sales_person_name` may be null. Use `message.driverid` for van requests; Sales Person IDs are separate identifiers.

Login with no active Van Session:
```json
{
  "full_name": "Sample Driver",
  "home_page": "/app/business-home",
  "message": {
    "driverid": "DRV-00001",
    "organizationid": "nesto",
    "sessionid": null,
    "status": "Success",
    "vanid": "VAN-00001"
  },
  "permissions": {
    "sales": false,
    "van_sales": true
  },
  "roles": [
    "Accounts User",
    "All",
    "Desk User",
    "Guest",
    "Van Sales User"
  ],
  "sales_person_id": null,
  "sales_person_name": null
}
```

When native login requires further authentication (endpoint message):
```json
{
  "message": {
    "status": "AuthenticationRequired",
    "detail": "Complete ERP password reset or two-factor authentication."
  }
}
```

Native two-factor/password-reset flows may also add their own verification fields. Login sets the authentication cookie in HTTP headers.

`roles` is the effective ERP role list. The top-level `permissions.sales` and `permissions.van_sales` booleans report enabled/disabled Retail areas using the same role, saved selection and blocked-module rules as Desk. These flags do not grant document Create/Write/Submit rights.

A user with Van Sales disabled can use standard `POST /api/method/login` (`usr`, `pwd`) to receive these flags; `driver_login` still requires Van Sales access and a driver assignment. Full standard-login example:
```json
{
  "full_name": "Sample Sales User",
  "home_page": "/app/business-home",
  "message": "Logged In",
  "permissions": {
    "sales": true,
    "van_sales": false
  },
  "roles": [
    "All",
    "Desk User",
    "Guest",
    "Sales User",
    "Van Sales User"
  ],
  "sales_person_id": null,
  "sales_person_name": null
}
```

### 2. Driver customer create/update

`POST /api/method/retail.api.van_sales.upsert_customer`

Request:
```json
{
  "requestid": "VAN01-CUST-001",
  "driverid": "DRV-00001",
  "organizationid": "nesto",
  "external_customer_id": "VAN01-CUST-001",
  "customerid": null,
  "customer_name": "Sample Customer",
  "mobile_no": "971500000000",
  "customer_group": "All Customer Groups",
  "territory": "All Territories",
  "email_id": "customer@example.com",
  "tax_id": "100000000000002"
}
```
Response:
```json
{
  "message": {
    "action": "Created",
    "customerid": "C-1",
    "driverid": "DRV-00001",
    "status": "Success"
  }
}
```
For updates, send the returned `customerid`. ERP assigns new customers to the authenticated driver and uses native Customer validation. A manager must assign existing customers using Customer → Van Driver before the driver can download or use them.

Update response:
```json
{
  "message": {
    "action": "Updated",
    "customerid": "C-1",
    "driverid": "DRV-00001",
    "status": "Success"
  }
}
```

### 3. Load stock requests

`GET /api/method/retail.api.van_sales.get_load_stock?driverid=DRV-00001&organizationid=nesto`

Response:
```json
{
  "message": {
    "loads": [
      {
        "items": [
          {
            "item_code": "I-1",
            "qty": 20.0,
            "request_itemid": "MR-ROW-001",
            "uom": "Nos"
          }
        ],
        "requestid": "MAT-MR-2026-00001",
        "source_warehouse": "Loading Stores - N",
        "target_warehouse": "Van 01 - N",
        "vanid": "VAN-00001"
      }
    ],
    "status": "Success"
  }
}
```

No pending loads:
```json
{
  "message": {
    "loads": [],
    "status": "Success"
  }
}
```

### 4. Confirm load

`POST /api/method/retail.api.van_sales.confirm_load`

Request:
```json
{
  "requestid": "VAN01-LOAD-001",
  "load_requestid": "MAT-MR-2026-00001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001"
}
```
Response:
```json
{
  "message": {
    "docstatus": 1,
    "status": "Posted",
    "stock_entry": "MAT-STE-2026-00001"
  }
}
```
Transfers the approved load into the van warehouse. For tracked stock, optionally send `items: [{"request_itemid":"<load row ID>","batch_no":"<batch>","serial_no":"<serial1>\n<serial2>"}]`; quantities still come from the ERP request. `load_requestid` identifies the ERP load request; `requestid` identifies this confirmation action.

### 5. Unload stock

`POST /api/method/retail.api.van_sales.unload_stock`

Request:
```json
{
  "requestid": "VAN01-UNLOAD-001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001",
  "target_warehouse": "Loading Stores - N",
  "items": [
    {
      "item_code": "I-1",
      "qty": 5,
      "uom": "Nos"
    }
  ]
}
```
Response:
```json
{
  "message": {
    "docstatus": 1,
    "status": "Posted",
    "stock_entry": "MAT-STE-2026-00002"
  }
}
```
Transfers stock from the session's van warehouse to the van's configured Loading / Return Warehouse.

### 6. Start session

`POST /api/method/retail.api.van_sales.start_session`

Request:
```json
{
  "requestid": "VAN01-START-001",
  "driverid": "DRV-00001",
  "vanid": "VAN-00001",
  "organizationid": "nesto",
  "session_date": "2026-11-24",
  "timing": "2026-11-24 08:00:00",
  "opening_balance": 100.0,
  "sessionid": "VS-2026-00001",
  "opening_km": 12000
}
```
Response:
```json
{
  "message": {
    "session_status": "Open",
    "sessionid": "VS-2026-00001",
    "status": "Success"
  }
}
```
Reject creation if the driver or van already has an open session; the error text identifies the existing session. Preserve the selected business date separately from actual timestamps.

### 7. Break/resume

`POST /api/method/retail.api.van_sales.update_session_status`

Request:
```json
{
  "requestid": "VAN01-BREAK-001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001",
  "action": "break",
  "timing": "2026-11-24 12:00:00"
}
```
Response:
```json
{
  "message": {
    "activity_status": "Break",
    "sessionid": "VS-2026-00001",
    "status": "Success"
  }
}
```
For resume, send a new request ID with `action: "resume"`; response `activity_status` is `Active`. ERP stores mobile activity separately; the Van Session remains Open during a break. Each request and its timestamp remain in Van API Request history.

Resume response:
```json
{
  "message": {
    "activity_status": "Active",
    "sessionid": "VS-2026-00001",
    "status": "Success"
  }
}
```

### 8. End session

`POST /api/method/retail.api.van_sales.end_session`

Request:
```json
{
  "requestid": "VAN01-END-001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001",
  "timing": "2026-11-24 18:00:00",
  "closing_cash": 405.0,
  "closing_km": 12120,
  "collection_details": [
    {
      "mode_of_payment": "Cash",
      "amount": 305.0
    }
  ],
  "remarks": "Route completed"
}
```
Response:
```json
{
  "message": {
    "session_status": "Closed",
    "sessionid": "VS-2026-00001",
    "status": "Success"
  }
}
```
Collection details are closing totals, not instructions to create payments again. Sync sales, returns, payments, expenses and unloading before closing.

### 9. Active session information

`GET /api/method/retail.api.van_sales.get_active_session?driverid=DRV-00001`

Optional: `sessionid=VS-2026-00001`.

Response:
```json
{
  "message": {
    "session": {
      "activity_status": "Active",
      "close_time": null,
      "closing_cash": 0.0,
      "driverid": "DRV-00001",
      "open_time": "2026-11-24 13:37:17.288880",
      "opening_balance": 100.0,
      "organizationid": "nesto",
      "session_date": "2026-11-24",
      "session_status": "Open",
      "sessionid": "VS-2026-00001",
      "vanid": "VAN-00001",
      "warehouse": "Van 01 - N"
    },
    "status": "Success"
  }
}
```
No active session: `{"message":{"status":"Success","session":null}}`.

### 10. Sales invoice master/details

`GET /api/method/retail.api.van_sales.get_sales_invoice_data?driverid=DRV-00001&sessionid=VS-2026-00001`

Response:
```json
{
  "message": {
    "cost_center": "Main - N",
    "currency": "AED",
    "invoices": [
      {
        "currency": "AED",
        "customer_name": "Sample Customer",
        "customerid": "C-1",
        "docstatus": 1,
        "grand_total": 105.0,
        "invoiceid": "SINV-2026-00001",
        "outstanding_amount": 105.0,
        "posting_date": "2026-11-24"
      }
    ],
    "modes_of_payment": [
      "Bank Draft",
      "Card",
      "Cash",
      "Cheque",
      "Credit Card",
      "Cash",
      "Wire Transfer"
    ],
    "organizationid": "nesto",
    "selling_price_list": "Standard Selling",
    "status": "Success",
    "taxes_and_charges": null,
    "warehouse": "Van 01 - N"
  }
}
```
Optional `invoiceid` returns the full selected invoice including item and tax rows. Item, customer and pricing masters continue through the existing master download.

Single invoice request: add `invoiceid=SINV-2026-00001`. Full response:
```json
{
  "message": {
    "invoice": {
      "account_for_change_amount": null,
      "additional_discount_account": null,
      "additional_discount_percentage": 0.0,
      "address_display": null,
      "advances": [],
      "against_income_account": "Sales Account - N",
      "allocate_advances_automatically": 0,
      "amended_from": null,
      "amount_eligible_for_commission": 100.0,
      "apply_discount_on": "Grand Total",
      "auto_repeat": null,
      "base_change_amount": 0.0,
      "base_discount_amount": 0.0,
      "base_grand_total": 105.0,
      "base_in_words": "AED One Hundred And Five only.",
      "base_net_total": 100.0,
      "base_paid_amount": 0.0,
      "base_rounded_total": 0.0,
      "base_rounding_adjustment": 0.0,
      "base_total": 100.0,
      "base_total_taxes_and_charges": 5.0,
      "base_write_off_amount": 0.0,
      "campaign": null,
      "cash_bank_account": null,
      "change_amount": 0.0,
      "commission_rate": 0.0,
      "company": "nesto",
      "company_address": "Al Karama-Billing",
      "company_address_display": "Karama1<br>\nDubai<br>\nUnited Arab Emirates<br>\n<br>\nPhone: 989561237<br>Email: sample@gmail.com<br>",
      "company_contact_person": null,
      "company_tax_id": "789456123",
      "company_trn": "789456123",
      "contact_display": null,
      "contact_email": null,
      "contact_mobile": null,
      "contact_person": null,
      "conversion_rate": 1.0,
      "cost_center": "Main - N",
      "creation": "2026-11-24 13:37:19.351917",
      "currency": "AED",
      "custom_available_loyalty_points": 0,
      "custom_counter": null,
      "custom_counter_name": "",
      "custom_driver": "DRV-00001",
      "custom_driver_name": "Sample Driver",
      "custom_gift_voucher_amount": 0.0,
      "custom_gift_voucher_code": null,
      "custom_gift_voucher_discount_applied": 0.0,
      "custom_gift_voucher_redemption_reference": null,
      "custom_is_van_sale": 1,
      "custom_payment_revision": 0,
      "custom_retail_delivery_person": null,
      "custom_retail_sales_person": null,
      "custom_van": "VAN-00001",
      "custom_van_session": "VS-2026-00001",
      "custom_van_warehouse": "Van 01 - N",
      "custom_voucher_card_redeem_amount": 0.0,
      "customer": "C-1",
      "customer_address": null,
      "customer_group": "All Customer Groups",
      "customer_name": "Sample Customer",
      "customer_name_in_arabic": "",
      "debit_to": "Trade Receivable - N",
      "disable_rounded_total": 1,
      "discount_amount": 0.0,
      "dispatch_address": null,
      "dispatch_address_name": null,
      "docstatus": 1,
      "doctype": "Sales Invoice",
      "due_date": "2026-11-24",
      "from_date": null,
      "grand_total": 105.0,
      "group_same_items": 0,
      "idx": 0,
      "ignore_default_payment_terms_template": 0,
      "ignore_pricing_rule": 0,
      "in_words": "AED One Hundred And Five only.",
      "incoterm": null,
      "inter_company_invoice_reference": null,
      "is_cash_or_non_trade_discount": 0,
      "is_consolidated": 0,
      "is_debit_note": 0,
      "is_discounted": 0,
      "is_internal_customer": 0,
      "is_opening": "No",
      "is_pos": 0,
      "is_return": 0,
      "items": [
        {
          "actual_batch_qty": 0.0,
          "actual_qty": 20.0,
          "allow_zero_valuation_rate": 0,
          "amount": 100.0,
          "asset": null,
          "barcode": "2000000000084",
          "base_amount": 100.0,
          "base_net_amount": 100.0,
          "base_net_rate": 10.0,
          "base_price_list_rate": 0.0,
          "base_rate": 10.0,
          "base_rate_with_margin": 0.0,
          "batch_no": null,
          "brand": null,
          "company_total_stock": 0.0,
          "conversion_factor": 1.0,
          "cost_center": "Main - N",
          "creation": "2026-11-24 13:37:19.351917",
          "custom_amount_including_vat": 105.0,
          "custom_barcode_scan": null,
          "custom_buy_get_promotion": null,
          "custom_foc_key": null,
          "custom_foc_parent": null,
          "custom_foc_qty": 0.0,
          "custom_item_barcode": "2000000000084",
          "custom_packing_detail": null,
          "custom_rate_including_vat": 10.5,
          "custom_retail_transaction_identity": "{\"version\": 1, \"retail_transaction_uom\": \"Nos\", \"retail_transaction_barcode\": \"2000000000084\", \"retail_transaction_name\": \"Sample Item\", \"retail_transaction_qty\": 10.0, \"retail_transaction_factor\": 1.0, \"retail_identity_source\": \"Saved at submission; Recorded transaction\"}",
          "custom_total_stock_qty": 10.0,
          "custom_vat_amount": 5.0,
          "customer_item_code": null,
          "deferred_revenue_account": null,
          "delivered_by_supplier": 0,
          "delivered_qty": 0.0,
          "delivery_date": null,
          "delivery_note": null,
          "description": "Sample Item",
          "discount_account": null,
          "discount_amount": 0.0,
          "discount_percentage": 50.0,
          "distributed_discount_amount": 0.0,
          "dn_detail": null,
          "docstatus": 1,
          "doctype": "Sales Invoice Item",
          "enable_deferred_revenue": 0,
          "expense_account": "Cost of Goods Sold in Trading - N",
          "finance_book": null,
          "grant_commission": 1,
          "has_item_scanned": 0,
          "idx": 1,
          "image": "",
          "income_account": "Sales Account - N",
          "incoming_rate": 8.0,
          "is_exempt": 0,
          "is_fixed_asset": 0,
          "is_free_item": 0,
          "is_zero_rated": 0,
          "item_code": "I-1",
          "item_group": "KG",
          "item_name": "Sample Item",
          "item_tax_rate": "{}",
          "item_tax_template": null,
          "margin_rate_or_amount": 0.0,
          "margin_type": "Percentage",
          "modified": "2026-11-24 13:37:19.881004",
          "modified_by": "driver@example.com",
          "name": "abc123",
          "net_amount": 100.0,
          "net_rate": 10.0,
          "owner": "driver@example.com",
          "page_break": 0,
          "parent": "SINV-2026-00001",
          "parentfield": "items",
          "parenttype": "Sales Invoice",
          "pos_invoice": null,
          "pos_invoice_item": null,
          "price_list_rate": 0.0,
          "pricing_rules": "[\n \"PRLE-0039\"\n]",
          "project": null,
          "purchase_order": null,
          "purchase_order_item": null,
          "qty": 10.0,
          "quality_inspection": null,
          "rate": 10.0,
          "rate_with_margin": 0.0,
          "sales_invoice_item": null,
          "sales_order": null,
          "serial_and_batch_bundle": null,
          "serial_no": null,
          "service_end_date": null,
          "service_start_date": null,
          "service_stop_date": null,
          "so_detail": null,
          "stock_qty": 10.0,
          "stock_uom": "Nos",
          "stock_uom_rate": 10.0,
          "target_warehouse": null,
          "tax_amount": 5.0,
          "tax_code": "",
          "tax_rate": 5.0,
          "total_amount": 105.0,
          "total_weight": 0.0,
          "uom": "Nos",
          "use_serial_batch_fields": 0,
          "warehouse": "Van 01 - N",
          "weight_per_unit": 0.0,
          "weight_uom": null
        }
      ],
      "language": "en",
      "last_scanned_warehouse": null,
      "letter_head": "Arab Scale Letter Head - Standard",
      "loyalty_amount": 0.0,
      "loyalty_points": 0,
      "loyalty_program": "test loyalty",
      "loyalty_redemption_account": null,
      "loyalty_redemption_cost_center": null,
      "modified": "2026-11-24 13:37:19.881004",
      "modified_by": "driver@example.com",
      "name": "SINV-2026-00001",
      "named_place": null,
      "naming_series": "VS-.#",
      "net_total": 100.0,
      "only_include_allocated_payments": 0,
      "other_charges_calculation": "<div class=\"tax-break-up\" style=\"overflow-x: auto;\">\n\t<table class=\"table table-bordered table-hover\">\n\t\t<thead>\n\t\t\t<tr>\n\t\t\t\t\n\t\t\t\t\t\n\t\t\t\t\t\t<th class=\"text-left\">Item</th>\n\t\t\t\t\t\n\t\t\t\t\n\t\t\t\t\t\n\t\t\t\t\t\t<th class=\"text-right\">Taxable Amount</th>\n\t\t\t\t\t\n\t\t\t\t\n\t\t\t\t\t\n\t\t\t\t\t\t<th class=\"text-right\">Sales Tax [VAT 5% - N]</th>\n\t\t\t\t\t\n\t\t\t\t\n\t\t\t</tr>\n\t\t</thead>\n\t\t<tbody>\n\t\t\t\n\t\t\t\t<tr>\n\t\t\t\t\t<td>I-94</td>\n\t\t\t\t\t<td class=\"text-right\">\n\t\t\t\t\t\t\n\t\t\t\t\t\t\tد.إ 100.00\n\t\t\t\t\t\t\n\t\t\t\t\t</td>\n\t\t\t\t\t\n\t\t\t\t\t\t\n\t\t\t\t\t\t\n\t\t\t\t\t\t\t<td class=\"text-right\">\n\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t\t\t(5.0%)\n\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t\t\tد.إ 5.00\n\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t</td>\n\t\t\t\t\t\t\n\t\t\t\t\t\n\t\t\t\t</tr>\n\t\t\t\n\t\t</tbody>\n\t</table>\n</div>",
      "outstanding_amount": 105.0,
      "owner": "driver@example.com",
      "packed_items": [],
      "paid_amount": 0.0,
      "party_account_currency": "AED",
      "payment_schedule": [
        {
          "base_outstanding": 105.0,
          "base_paid_amount": 0.0,
          "base_payment_amount": 105.0,
          "creation": "2026-11-24 13:37:19.623431",
          "credit_days": 0,
          "credit_months": 0,
          "description": null,
          "discount": 0.0,
          "discount_date": null,
          "discount_type": null,
          "discount_validity": 0,
          "discount_validity_based_on": null,
          "discounted_amount": 0.0,
          "docstatus": 1,
          "doctype": "Payment Schedule",
          "due_date": "2026-11-24",
          "due_date_based_on": null,
          "idx": 1,
          "invoice_portion": 100.0,
          "mode_of_payment": null,
          "modified": "2026-11-24 13:37:19.881004",
          "modified_by": "driver@example.com",
          "name": "30s35p8kbj",
          "outstanding": 105.0,
          "owner": "driver@example.com",
          "paid_amount": 0.0,
          "parent": "SINV-2026-00001",
          "parentfield": "payment_schedule",
          "parenttype": "Sales Invoice",
          "payment_amount": 105.0,
          "payment_term": null
        }
      ],
      "payment_terms_template": null,
      "payments": [],
      "permit_no": null,
      "plc_conversion_rate": 1.0,
      "po_date": null,
      "po_no": "",
      "pos_profile": null,
      "posting_date": "2026-11-24",
      "posting_time": "13:37:19.90735",
      "price_list_currency": "AED",
      "pricing_rules": [
        {
          "child_docname": "abc123",
          "creation": "2026-11-24 13:37:19.981227",
          "docstatus": 1,
          "doctype": "Pricing Rule Detail",
          "idx": 1,
          "item_code": "I-1",
          "margin_type": null,
          "modified": "2026-11-24 13:37:19.981227",
          "modified_by": "driver@example.com",
          "name": "30vch90981",
          "owner": "driver@example.com",
          "parent": "SINV-2026-00001",
          "parentfield": "pricing_rules",
          "parenttype": "Sales Invoice",
          "pricing_rule": "PRLE-0039",
          "rate_or_discount": null,
          "rule_applied": 1
        }
      ],
      "project": null,
      "redeem_loyalty_points": 0,
      "remarks": "No Remarks",
      "represents_company": null,
      "return_against": null,
      "rounded_total": 0.0,
      "rounding_adjustment": 0.0,
      "sales_partner": null,
      "sales_team": [],
      "scan_barcode": null,
      "select_print_heading": null,
      "selling_price_list": "Standard Selling",
      "set_posting_time": 0,
      "set_target_warehouse": null,
      "set_warehouse": "Van 01 - N",
      "shipping_address": null,
      "shipping_address_name": null,
      "shipping_rule": null,
      "source": null,
      "status": "Unpaid",
      "subscription": null,
      "tax_category": "",
      "tax_id": null,
      "taxes": [
        {
          "account_currency": null,
          "account_head": "VAT 5% - N",
          "base_tax_amount": 5.0,
          "base_tax_amount_after_discount_amount": 5.0,
          "base_total": 105.0,
          "charge_type": "On Net Total",
          "cost_center": "Main - N",
          "creation": "2026-11-24 13:37:19.979856",
          "description": "Sales Tax [VAT 5% - N]",
          "docstatus": 1,
          "doctype": "Sales Taxes and Charges",
          "dont_recompute_tax": 0,
          "idx": 1,
          "included_in_paid_amount": 0,
          "included_in_print_rate": 0,
          "item_wise_tax_detail": "{\"I-94\":[5.0,5.0]}",
          "modified": "2026-11-24 13:37:19.979856",
          "modified_by": "driver@example.com",
          "name": "30v6h7nc6d",
          "owner": "driver@example.com",
          "parent": "SINV-2026-00001",
          "parentfield": "taxes",
          "parenttype": "Sales Invoice",
          "project": null,
          "rate": 5.0,
          "row_id": null,
          "tax_amount": 5.0,
          "tax_amount_after_discount_amount": 5.0,
          "total": 105.0
        }
      ],
      "taxes_and_charges": null,
      "tc_name": null,
      "terms": null,
      "territory": "All Territories",
      "timesheets": [],
      "title": "Sample Customer",
      "to_date": null,
      "total": 100.0,
      "total_advance": 0.0,
      "total_billing_amount": 0.0,
      "total_billing_hours": 0.0,
      "total_commission": 0.0,
      "total_net_weight": 0.0,
      "total_qty": 10.0,
      "total_taxes_and_charges": 5.0,
      "tourist_tax_return": 0.0,
      "unrealized_profit_loss_account": null,
      "update_billed_amount_in_delivery_note": 1,
      "update_billed_amount_in_sales_order": 0,
      "update_outstanding_for_self": 1,
      "update_stock": 1,
      "use_company_roundoff_cost_center": 0,
      "vat_emirate": "Dubai",
      "write_off_account": null,
      "write_off_amount": 0.0,
      "write_off_cost_center": null,
      "write_off_outstanding_amount_automatically": 0
    },
    "status": "Success"
  }
}
```

### 11. Save/submit sale

`POST /api/method/retail.api.van_sales.post_sale`

Compatibility route: `POST /api/method/retail.api.pos_sync.post_sale`. Send a flat JSON body.

Request:
```json
{
  "requestid": "RG1234-SALE-20261125-001",
  "driverid": "DR-4",
  "sessionid": "VSS-6",
  "organizationid": "nesto",
  "vanid": "RG1234",
  "warehouse": "V4W - N",
  "action": "submit",
  "invoiceid": null,
  "customerid": "C-1",
  "posting_date": "2026-11-25",
  "posting_time": "10:00:00",
  "selling_price_list": "Standard Selling",
  "taxes_and_charges": "UAE VAT 5% - N",
  "apply_discount_on": "Grand Total",
  "discount_amount": 0,
  "items": [
    {
      "item_code": "I-57",
      "barcode": "478566",
      "qty": 1,
      "uom": "Nos",
      "rate": 35,
      "discount_percentage": 0,
      "discount_amount": 0,
      "rate_includes_vat": 1
    }
  ],
  "payments": [
    {
      "mode_of_payment": "CASH",
      "amount": 35
    }
  ],
  "remarks": "Route sale"
}
```
Response:
```json
{
  "message": {
    "docstatus": 1,
    "grand_total": 35.0,
    "invoiceid": "SINV-2026-00001",
    "outstanding_amount": 0.0,
    "paymentids": ["ACC-PAY-2026-00001"],
    "status": "Posted"
  }
}
```
Sample assumes configured 5% item VAT and matching van price list, tax template, eligible Van Sales customer and payment mode. The rate of 35 includes VAT, so ERP calculates a grand total of 35. `grand_total` is returned in the response; it is not a supported request input. Send `payments: []` for an unpaid sale.

Fetch `vanid`, `organizationid` and `warehouse` from the assigned session; these example values are not defaults. Supplied values must match the assignment. Do not use the POS `company`/`counter`/`payload` envelope. Counter, cashier, shift and terminal fields are not required. `delivery_charge` is not supported. ERP sets `update_stock: 1` and derives the company and UOM conversion factors. Send item `batch_no` or `serial_no` when required. `remarks` currently passes to generated payment entries; it is not explicitly saved on the Sales Invoice.

To update/submit a saved draft, send its `invoiceid` and a new action request ID. Posted invoices cannot be edited through this endpoint.

Invoice discount keys (top-level `post_sale`):

| Key | Values |
| --- | --- |
| `apply_discount_on` | `Net Total` or `Grand Total` (default for a new discount) |
| `additional_discount_percentage` | `0`–`100`; send instead of a nonzero `discount_amount` |
| `discount_amount` | Nonnegative invoice discount; send instead of a nonzero percentage |

Percentage discount request:
```json
{
  "requestid": "VAN01-SALE-DISCOUNT-001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001",
  "customerid": "C-1",
  "action": "submit",
  "apply_discount_on": "Grand Total",
  "additional_discount_percentage": 10,
  "items": [{"item_code": "I-1", "qty": 10, "uom": "Nos", "rate": 10, "rate_includes_vat": 0}],
  "payments": []
}
```

Fixed invoice discount: replace `additional_discount_percentage` with `"discount_amount": 5`. On a draft update, send `discount_amount: 0` to clear the invoice discount; omitting all three keys preserves it. ERP calculates tax, totals and outstanding amounts. The response keys remain unchanged.

Eligible configured Promo Prices apply through ERP invoice validation; matching fixed promotional prices replace the item rate and clear its item discount fields before invoice-level discounts are calculated.

Draft response (`action: "draft"`):
```json
{
  "message": {
    "docstatus": 0,
    "grand_total": 105.0,
    "invoiceid": "SINV-2026-00001",
    "outstanding_amount": 105.0,
    "paymentids": [],
    "status": "Draft"
  }
}
```

Identical submitted-sale retry:
```json
{
  "message": {
    "docstatus": 1,
    "duplicate": true,
    "grand_total": 105.0,
    "invoiceid": "SINV-2026-00001",
    "outstanding_amount": 105.0,
    "paymentids": [],
    "status": "Posted"
  }
}
```

Paid sale response (example values; `payments` supplied):
```json
{
  "message": {
    "docstatus": 1,
    "grand_total": 105.0,
    "invoiceid": "SINV-2026-00002",
    "outstanding_amount": 0.0,
    "paymentids": [
      "ACC-PAY-2026-00003"
    ],
    "status": "Posted"
  }
}
```

### 12. Sales return master/details

`GET /api/method/retail.api.van_sales.get_sales_return_data?driverid=DRV-00001&sessionid=VS-2026-00001&invoiceid=SINV-2026-00001`

Response:
```json
{
  "message": {
    "customerid": "C-1",
    "invoiceid": "SINV-2026-00001",
    "items": [
      {
        "invoice_itemid": "abc123",
        "item_code": "I-1",
        "rate": 10.0,
        "returnable_qty": 9.0,
        "returned_qty": 1.0,
        "sold_qty": 10.0,
        "uom": "Nos"
      }
    ],
    "status": "Success"
  }
}
```

Optional `returnid` returns the full selected draft/submitted return in `message.return_invoice`.

List returns: omit `invoiceid` and `returnid`:
```json
{
  "message": {
    "returns": [
      {
        "currency": "AED",
        "customer_name": "Sample Customer",
        "customerid": "C-1",
        "docstatus": 1,
        "grand_total": -10.5,
        "invoiceid": "SINV-RET-2026-00001",
        "outstanding_amount": -10.5,
        "posting_date": "2026-11-24"
      }
    ],
    "status": "Success"
  }
}
```

Single return request: add `returnid=SINV-RET-2026-00001`. Full response:
```json
{
  "message": {
    "return_invoice": {
      "account_for_change_amount": null,
      "additional_discount_account": null,
      "additional_discount_percentage": 0.0,
      "address_display": null,
      "advances": [],
      "against_income_account": "Sales Account - N",
      "allocate_advances_automatically": 0,
      "amended_from": null,
      "amount_eligible_for_commission": -10.0,
      "apply_discount_on": "Grand Total",
      "auto_repeat": null,
      "base_change_amount": 0.0,
      "base_discount_amount": 0.0,
      "base_grand_total": -10.5,
      "base_in_words": "AED Ten and Fifty Fils only.",
      "base_net_total": -10.0,
      "base_paid_amount": 0.0,
      "base_rounded_total": 0.0,
      "base_rounding_adjustment": 0.0,
      "base_total": -10.0,
      "base_total_taxes_and_charges": -0.5,
      "base_write_off_amount": 0.0,
      "campaign": null,
      "cash_bank_account": null,
      "change_amount": 0.0,
      "commission_rate": 0.0,
      "company": "nesto",
      "company_address": "Al Karama-Billing",
      "company_address_display": "Karama1<br>\nDubai<br>\nUnited Arab Emirates<br>\n<br>\nPhone: 989561237<br>Email: sample@gmail.com<br>",
      "company_contact_person": null,
      "company_tax_id": "789456123",
      "company_trn": "789456123",
      "contact_display": null,
      "contact_email": null,
      "contact_mobile": null,
      "contact_person": null,
      "conversion_rate": 1.0,
      "cost_center": "Main - N",
      "creation": "2026-11-24 13:37:20.446605",
      "currency": "AED",
      "custom_available_loyalty_points": 5,
      "custom_counter": null,
      "custom_counter_name": "",
      "custom_driver": "DRV-00001",
      "custom_driver_name": "Sample Driver",
      "custom_gift_voucher_amount": 0.0,
      "custom_gift_voucher_code": null,
      "custom_gift_voucher_discount_applied": 0.0,
      "custom_gift_voucher_redemption_reference": null,
      "custom_is_van_sale": 1,
      "custom_payment_revision": 0,
      "custom_retail_delivery_person": null,
      "custom_retail_sales_person": null,
      "custom_van": "VAN-00001",
      "custom_van_session": "VS-2026-00001",
      "custom_van_warehouse": "Van 01 - N",
      "custom_voucher_card_redeem_amount": 0.0,
      "customer": "C-1",
      "customer_address": null,
      "customer_group": "All Customer Groups",
      "customer_name": "Sample Customer",
      "customer_name_in_arabic": "",
      "debit_to": "Trade Receivable - N",
      "disable_rounded_total": 1,
      "discount_amount": 0.0,
      "dispatch_address": null,
      "dispatch_address_name": null,
      "docstatus": 1,
      "doctype": "Sales Invoice",
      "due_date": "2026-11-24",
      "from_date": null,
      "grand_total": -10.5,
      "group_same_items": 0,
      "idx": 0,
      "ignore_default_payment_terms_template": 0,
      "ignore_pricing_rule": 1,
      "in_words": "AED Ten and Fifty Fils only.",
      "incoterm": null,
      "inter_company_invoice_reference": null,
      "is_cash_or_non_trade_discount": 0,
      "is_consolidated": 0,
      "is_debit_note": 0,
      "is_discounted": 0,
      "is_internal_customer": 0,
      "is_opening": "No",
      "is_pos": 0,
      "is_return": 1,
      "items": [
        {
          "actual_batch_qty": 0.0,
          "actual_qty": 10.0,
          "allow_zero_valuation_rate": 0,
          "amount": -10.0,
          "asset": null,
          "barcode": "2000000000084",
          "base_amount": -10.0,
          "base_net_amount": -10.0,
          "base_net_rate": 10.0,
          "base_price_list_rate": 0.0,
          "base_rate": 10.0,
          "base_rate_with_margin": 0.0,
          "batch_no": null,
          "brand": null,
          "company_total_stock": 0.0,
          "conversion_factor": 1.0,
          "cost_center": "Main - N",
          "creation": "2026-11-24 13:37:20.446605",
          "custom_amount_including_vat": -10.5,
          "custom_barcode_scan": null,
          "custom_buy_get_promotion": null,
          "custom_foc_key": null,
          "custom_foc_parent": null,
          "custom_foc_qty": 0.0,
          "custom_item_barcode": "2000000000084",
          "custom_packing_detail": null,
          "custom_rate_including_vat": 10.5,
          "custom_retail_transaction_identity": "{\"version\": 1, \"retail_transaction_uom\": \"Nos\", \"retail_transaction_barcode\": \"2000000000084\", \"retail_transaction_name\": \"Sample Item\", \"retail_transaction_qty\": -1.0, \"retail_transaction_factor\": 1.0, \"retail_identity_source\": \"Saved at submission; Recorded transaction\"}",
          "custom_total_stock_qty": -1.0,
          "custom_vat_amount": -0.5,
          "customer_item_code": null,
          "deferred_revenue_account": null,
          "delivered_by_supplier": 0,
          "delivered_qty": 0.0,
          "delivery_date": null,
          "delivery_note": null,
          "description": "Sample Item",
          "discount_account": null,
          "discount_amount": 0.0,
          "discount_percentage": 0.0,
          "distributed_discount_amount": 0.0,
          "dn_detail": null,
          "docstatus": 1,
          "doctype": "Sales Invoice Item",
          "enable_deferred_revenue": 0,
          "expense_account": "Cost of Goods Sold in Trading - N",
          "finance_book": null,
          "grant_commission": 1,
          "has_item_scanned": 0,
          "idx": 1,
          "image": "",
          "income_account": "Sales Account - N",
          "incoming_rate": 8.0,
          "is_exempt": 0,
          "is_fixed_asset": 0,
          "is_free_item": 0,
          "is_zero_rated": 0,
          "item_code": "I-1",
          "item_group": "KG",
          "item_name": "Sample Item",
          "item_tax_rate": "{}",
          "item_tax_template": null,
          "margin_rate_or_amount": 0.0,
          "margin_type": "Percentage",
          "modified": "2026-11-24 13:37:20.996770",
          "modified_by": "driver@example.com",
          "name": "3186tbekdc",
          "net_amount": -10.0,
          "net_rate": 10.0,
          "owner": "driver@example.com",
          "page_break": 0,
          "parent": "SINV-RET-2026-00001",
          "parentfield": "items",
          "parenttype": "Sales Invoice",
          "pos_invoice": null,
          "pos_invoice_item": null,
          "price_list_rate": 0.0,
          "pricing_rules": "",
          "project": null,
          "purchase_order": null,
          "purchase_order_item": null,
          "qty": -1.0,
          "quality_inspection": null,
          "rate": 10.0,
          "rate_with_margin": 0.0,
          "sales_invoice_item": "abc123",
          "sales_order": null,
          "serial_and_batch_bundle": null,
          "serial_no": null,
          "service_end_date": null,
          "service_start_date": null,
          "service_stop_date": null,
          "so_detail": null,
          "stock_qty": -1.0,
          "stock_uom": "Nos",
          "stock_uom_rate": 10.0,
          "target_warehouse": null,
          "tax_amount": -0.5,
          "tax_code": "",
          "tax_rate": 5.0,
          "total_amount": -10.5,
          "total_weight": 0.0,
          "uom": "Nos",
          "use_serial_batch_fields": 0,
          "warehouse": "Van 01 - N",
          "weight_per_unit": 0.0,
          "weight_uom": null
        }
      ],
      "language": "en",
      "last_scanned_warehouse": null,
      "letter_head": "Arab Scale Letter Head - Standard",
      "loyalty_amount": 0.0,
      "loyalty_points": 0,
      "loyalty_program": "test loyalty",
      "loyalty_redemption_account": null,
      "loyalty_redemption_cost_center": null,
      "modified": "2026-11-24 13:37:20.996770",
      "modified_by": "driver@example.com",
      "name": "SINV-RET-2026-00001",
      "named_place": null,
      "naming_series": "VS-.#",
      "net_total": -10.0,
      "only_include_allocated_payments": 0,
      "other_charges_calculation": "<div class=\"tax-break-up\" style=\"overflow-x: auto;\">\n\t<table class=\"table table-bordered table-hover\">\n\t\t<thead>\n\t\t\t<tr>\n\t\t\t\t\n\t\t\t\t\t\n\t\t\t\t\t\t<th class=\"text-left\">Item</th>\n\t\t\t\t\t\n\t\t\t\t\n\t\t\t\t\t\n\t\t\t\t\t\t<th class=\"text-right\">Taxable Amount</th>\n\t\t\t\t\t\n\t\t\t\t\n\t\t\t\t\t\n\t\t\t\t\t\t<th class=\"text-right\">Sales Tax [VAT 5% - N]</th>\n\t\t\t\t\t\n\t\t\t\t\n\t\t\t</tr>\n\t\t</thead>\n\t\t<tbody>\n\t\t\t\n\t\t\t\t<tr>\n\t\t\t\t\t<td>I-94</td>\n\t\t\t\t\t<td class=\"text-right\">\n\t\t\t\t\t\t\n\t\t\t\t\t\t\tد.إ 10.00\n\t\t\t\t\t\t\n\t\t\t\t\t</td>\n\t\t\t\t\t\n\t\t\t\t\t\t\n\t\t\t\t\t\t\n\t\t\t\t\t\t\t<td class=\"text-right\">\n\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t\t\t(5.0%)\n\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t\t\tد.إ 0.50\n\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t</td>\n\t\t\t\t\t\t\n\t\t\t\t\t\n\t\t\t\t</tr>\n\t\t\t\n\t\t</tbody>\n\t</table>\n</div>",
      "outstanding_amount": -10.5,
      "owner": "driver@example.com",
      "packed_items": [],
      "paid_amount": 0.0,
      "party_account_currency": "AED",
      "payment_schedule": [],
      "payment_terms_template": "",
      "payments": [],
      "permit_no": null,
      "plc_conversion_rate": 1.0,
      "po_date": null,
      "po_no": "",
      "pos_profile": null,
      "posting_date": "2026-11-24",
      "posting_time": "13:37:21.050859",
      "price_list_currency": "AED",
      "pricing_rules": [],
      "project": null,
      "redeem_loyalty_points": 0,
      "remarks": "No Remarks",
      "represents_company": null,
      "return_against": "SINV-2026-00001",
      "rounded_total": 0.0,
      "rounding_adjustment": 0.0,
      "sales_partner": null,
      "sales_team": [],
      "scan_barcode": null,
      "select_print_heading": "Credit Note",
      "selling_price_list": "Standard Selling",
      "set_posting_time": 0,
      "set_target_warehouse": null,
      "set_warehouse": "Van 01 - N",
      "shipping_address": null,
      "shipping_address_name": null,
      "shipping_rule": null,
      "source": null,
      "status": "Return",
      "subscription": null,
      "tax_category": "",
      "tax_id": null,
      "taxes": [
        {
          "account_currency": null,
          "account_head": "VAT 5% - N",
          "base_tax_amount": -0.5,
          "base_tax_amount_after_discount_amount": -0.5,
          "base_total": -10.5,
          "charge_type": "On Net Total",
          "cost_center": "Main - N",
          "creation": "2026-11-24 13:37:21.177450",
          "description": "Sales Tax [VAT 5% - N]",
          "docstatus": 1,
          "doctype": "Sales Taxes and Charges",
          "dont_recompute_tax": 0,
          "idx": 1,
          "included_in_paid_amount": 0,
          "included_in_print_rate": 0,
          "item_wise_tax_detail": "{\"I-94\":[5.0,-0.5]}",
          "modified": "2026-11-24 13:37:21.177450",
          "modified_by": "driver@example.com",
          "name": "31ba33v0i1",
          "owner": "driver@example.com",
          "parent": "SINV-RET-2026-00001",
          "parentfield": "taxes",
          "parenttype": "Sales Invoice",
          "project": null,
          "rate": 5.0,
          "row_id": null,
          "tax_amount": -0.5,
          "tax_amount_after_discount_amount": -0.5,
          "total": -10.5
        }
      ],
      "taxes_and_charges": null,
      "tc_name": null,
      "terms": null,
      "territory": "All Territories",
      "timesheets": [],
      "title": "Sample Customer",
      "to_date": null,
      "total": -10.0,
      "total_advance": 0.0,
      "total_billing_amount": 0.0,
      "total_billing_hours": 0.0,
      "total_commission": 0.0,
      "total_net_weight": 0.0,
      "total_qty": -1.0,
      "total_taxes_and_charges": -0.5,
      "tourist_tax_return": 0.0,
      "unrealized_profit_loss_account": null,
      "update_billed_amount_in_delivery_note": 1,
      "update_billed_amount_in_sales_order": 0,
      "update_outstanding_for_self": 1,
      "update_stock": 1,
      "use_company_roundoff_cost_center": 0,
      "vat_emirate": "Dubai",
      "write_off_account": null,
      "write_off_amount": 0.0,
      "write_off_cost_center": null,
      "write_off_outstanding_amount_automatically": 0
    },
    "status": "Success"
  }
}
```

### 13. Save/submit sales return

`POST /api/method/retail.api.van_sales.post_sales_return`

Request:
```json
{
  "requestid": "VAN01-RETURN-001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001",
  "action": "submit",
  "returnid": null,
  "invoiceid": "SINV-2026-00001",
  "posting_date": "2026-11-24",
  "items": [
    {
      "invoice_itemid": "abc123",
      "item_code": "I-1",
      "qty": -1,
      "uom": "Nos"
    }
  ]
}
```
Response:
```json
{
  "message": {
    "docstatus": 1,
    "grand_total": -10.5,
    "returnid": "SINV-RET-2026-00001",
    "status": "Posted"
  }
}
```
Returns use original invoice prices/taxes and negative quantities. A return creates a separate outstanding credit note; it does not automatically collect or refund money. For a cash refund, call `post_customer_payment` with `payment_type: "Pay"`, the return invoice ID and positive amount/allocation values. Ordinary collections use the default `payment_type: "Receive"`.

Draft return response (`action: "draft"`):
```json
{
  "message": {
    "docstatus": 0,
    "grand_total": -10.5,
    "returnid": "SINV-RET-2026-00001",
    "status": "Draft"
  }
}
```

### 14. Driver credit customers

`GET /api/method/retail.api.van_sales.get_credit_customers?driverid=DRV-00001&organizationid=nesto`

Response:
```json
{
  "message": {
    "customers": [
      {
        "currency": "AED",
        "customer_name": "Sample Customer",
        "customerid": "C-1",
        "outstanding_amount": 94.5
      }
    ],
    "status": "Success"
  }
}
```
Returns the net outstanding amount of submitted van invoices/credit notes visible for the assigned driver and company; it is not a full customer general-ledger statement.

### 15. Customer payment invoice details

`GET /api/method/retail.api.van_sales.get_customer_payment_data?driverid=DRV-00001&sessionid=VS-2026-00001&customerid=C-1`

Response:
```json
{
  "message": {
    "credit_notes": [
      {
        "available_amount": 10.5,
        "invoiceid": "SINV-RET-2026-00001"
      }
    ],
    "currency": "AED",
    "customerid": "C-1",
    "invoices": [
      {
        "currency": "AED",
        "customer_name": "Sample Customer",
        "customerid": "C-1",
        "docstatus": 1,
        "grand_total": 105.0,
        "invoiceid": "SINV-2026-00001",
        "outstanding_amount": 105.0,
        "posting_date": "2026-11-24"
      }
    ],
    "modes_of_payment": [
      "Bank Draft",
      "Card",
      "Cash",
      "Cheque",
      "Credit Card",
      "Cash",
      "Wire Transfer"
    ],
    "status": "Success"
  }
}
```
An available credit note is separate from an invoice's outstanding balance until allocated.

Session payment list: omit `customerid`:
```json
{
  "message": {
    "currency": "AED",
    "modes_of_payment": [
      "Bank Draft",
      "Card",
      "Cash",
      "Cheque",
      "Credit Card",
      "Cash",
      "Wire Transfer"
    ],
    "payments": [
      {
        "amount": 10.5,
        "customerid": "C-1",
        "docstatus": 1,
        "mode_of_payment": "Cash",
        "paymentid": "ACC-PAY-2026-00002",
        "posting_date": "2026-11-24"
      },
      {
        "amount": 105.0,
        "customerid": "C-1",
        "docstatus": 1,
        "mode_of_payment": "Cash",
        "paymentid": "ACC-PAY-2026-00001",
        "posting_date": "2026-11-24"
      }
    ],
    "status": "Success"
  }
}
```

### 16. Customer payment

`POST /api/method/retail.api.van_sales.post_customer_payment`

Request:
```json
{
  "requestid": "VAN01-PAY-001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001",
  "customerid": "C-1",
  "posting_date": "2026-11-24",
  "mode_of_payment": "Cash",
  "amount": 105.0,
  "payment_type": "Receive",
  "references": [
    {
      "invoiceid": "SINV-2026-00001",
      "allocated_amount": 105.0
    }
  ],
  "remarks": "Invoice collection"
}
```
Response:
```json
{
  "message": {
    "amount": 105.0,
    "docstatus": 1,
    "paymentid": "ACC-PAY-2026-00001",
    "status": "Posted"
  }
}
```
Validate current outstanding amounts and customer ownership before posting. Credit-note allocation is not a cash collection.

Refund request:
```json
{
  "requestid": "VAN01-REFUND-001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001",
  "customerid": "C-1",
  "posting_date": "2026-11-24",
  "mode_of_payment": "Cash",
  "amount": 10.5,
  "payment_type": "Pay",
  "references": [
    {
      "invoiceid": "SINV-RET-2026-00001",
      "allocated_amount": 10.5
    }
  ],
  "remarks": "Return refund"
}
```

Refund response (`payment_type: "Pay"`, references contain the return ID):
```json
{
  "message": {
    "amount": 10.5,
    "docstatus": 1,
    "paymentid": "ACC-PAY-2026-00002",
    "status": "Posted"
  }
}
```

### 17. Expense types/details

`GET /api/method/retail.api.van_sales.get_expense_data?driverid=DRV-00001&sessionid=VS-2026-00001`

Response:
```json
{
  "message": {
    "currency": "AED",
    "expense_types": [
      {
        "expense_type": "Fuel",
        "proof_required": 0
      }
    ],
    "expenses": [
      {
        "accounting_reference": "ACC-JV-2026-00001",
        "amount": 5.0,
        "docstatus": 1,
        "expense_type": "Fuel",
        "expenseid": "VEXP-00001",
        "mode_of_payment": "Cash",
        "proof_url": null,
        "remarks": "Fuel"
      }
    ],
    "status": "Success"
  }
}
```
Configure enabled Van Expense Type records with a company, expense account and proof requirement. Submitted Van Expense records create a balanced Journal Entry against the selected payment mode account.

### 18. Upload expense proof — existing upload API

`POST /api/method/upload_file` with authenticated `multipart/form-data`:

```text
file: <receipt file bytes>
is_private: 1
```
Response:
```json
{
  "message": {
    "content_hash": "1fb374ce3761e054c4f696647aee87c4",
    "creation": "2026-11-24 13:37:28.943481",
    "custom_document_code": "F-78",
    "docstatus": 0,
    "doctype": "File",
    "file_name": "receipt.txt",
    "file_size": 28,
    "file_type": "TXT",
    "file_url": "/private/files/receipt.txt",
    "folder": "Home",
    "idx": 0,
    "is_attachments_folder": 0,
    "is_folder": 0,
    "is_home_folder": 0,
    "is_private": 1,
    "modified": "2026-11-24 13:37:28.943481",
    "modified_by": "driver@example.com",
    "name": "FILE-00001",
    "owner": "driver@example.com",
    "uploaded_to_dropbox": 0,
    "uploaded_to_google_drive": 0
  }
}
```
Send the returned file URL in the expense request. The expense API checks private-file ownership and attaches the receipt to the submitted expense.

### 19. Expense entry

`POST /api/method/retail.api.van_sales.post_expense`

Request:
```json
{
  "requestid": "VAN01-EXP-001",
  "driverid": "DRV-00001",
  "sessionid": "VS-2026-00001",
  "posting_date": "2026-11-24",
  "expense_type": "Fuel",
  "amount": 50.0,
  "mode_of_payment": "Cash",
  "proof_url": "/private/files/receipt.txt",
  "remarks": "Route fuel"
}
```
Response:
```json
{
  "message": {
    "accounting_reference": "ACC-JV-2026-00001",
    "docstatus": 1,
    "expenseid": "VEXP-00001",
    "status": "Posted"
  }
}
```
ERP returns the saved Van Expense and its submitted Journal Entry IDs. Drivers do not need unrestricted Journal Entry permissions.

## Errors and identical retries

Van APIs use standard Frappe error responses with non-2xx HTTP statuses.

Actual permission-error response (HTTP 403), with sample values:
```json
{
  "_server_messages": "[\"{\\\"message\\\": \\\"You do not have permission to perform this action. Please contact the software team.\\\", \\\"title\\\": \\\"Permission Required\\\", \\\"indicator\\\": \\\"red\\\"}\"]",
  "exc_type": "PermissionError",
  "exception": "frappe.exceptions.PermissionError: You do not have permission to perform this action. Please contact the software team."
}
```

Validation errors usually use HTTP 417 with `exception`, `exc_type`, and optional `exc` / `_server_messages` diagnostic fields. Those native diagnostics vary with the error and site configuration.

For every posting endpoint, an identical successful retry returns every original response field plus `message.duplicate: true`; it does not post again. An example is included under Save/submit sale. Read endpoints return empty arrays when no rows match, while keeping the same remaining fields. No active session returns `{"message":{"status":"Success","session":null}}`.

Sales, return and unload rows accept `batch_no` and newline-separated `serial_no`. Batch/serial tracked stock must include the required ERP tracking details.

## Download all full examples

[VAN_SALES_API_RESPONSES.json](VAN_SALES_API_RESPONSES.json) contains complete request/response pairs, including list/detail, draft/submitted, empty and retry cases, plus a labeled paid-sale illustration. Compatibility routes return exactly the same bodies as their canonical van endpoints; the captured app aliases are also included in this file. Authentication headers and cookies are not body fields. The values are sanitized samples; no real credentials or PIN hashes are included.

## Deployment and validation

Installed on `retail-test.localhost` on 24 November 2026. The five formerly missing `pos_sync` routes resolve over local HTTP and require authentication. Other servers, including the supplied ngrok address, have not been independently verified.

Posting, stock balances, balanced GL entries, invoice/return drafts and submission, collections/refunds, expenses, unloading, duplicate protection and driver ownership are verified using a disposable database/Redis clone. HTTP checks cover native password login, cookie/token requests, compatibility routes and private receipt upload. Only the license-seat check is mocked for synthetic test users; production licensing code/state is unchanged. Existing POS master response keys and catalog contents match the pre-change implementation. Installation preserved business record counts and existing Account permissions.

"""Administrator/Super Admin corrections without changing terminal receipts."""
import json

import frappe
from frappe.utils import now_datetime

from retail.access_control import is_super_admin, require_super_admin
from retail.pos_operations import canonical

DOCTYPES = ("POS Sync Log", "POS Accepted Transaction", "POS Settlement Allocation", "POS Settlement Exception")
SALE_TYPES = {"POS Sale", "Sales Invoice", "Credit Sales Invoice", "POS Return", "Return"}


def effective_payload(transaction):
    return frappe._dict(json.loads(transaction.get("correction_payload_json") or transaction.payload_json))


def transaction_name(doc):
    if doc.doctype == "POS Accepted Transaction":
        return doc.name
    if doc.doctype == "POS Sync Log":
        if doc.sync_type not in SALE_TYPES:
            frappe.throw("Payload correction and posting are supported for POS sale and return logs.")
        return frappe.db.get_value("POS Accepted Transaction", {"external_pos_reference": doc.external_reference}, "name")
    return doc.transaction


def load_correction(doc):
    if not is_super_admin() or doc.is_new():
        return
    if doc.doctype == "POS Sync Log":
        if doc.sync_type in SALE_TYPES:
            name = transaction_name(doc)
            if name:
                transaction = frappe.get_doc("POS Accepted Transaction", name)
                doc.set_onload("correction_modified", str(transaction.modified))
                value, payload = parse_payload(doc.request_json)
                current = effective_payload(transaction)
                if canonical(payload) != canonical(current):
                    if "payload" in value:
                        value["payload"] = current
                    else:
                        value = current
                    doc.request_json = json.dumps(value, indent=2)
        return
    name = transaction_name(doc)
    if name:
        transaction = doc if doc.doctype == "POS Accepted Transaction" else frappe.get_doc("POS Accepted Transaction", name)
        if doc.doctype != "POS Accepted Transaction" or not doc.get("correction_payload_json"):
            doc.correction_payload_json = json.dumps(effective_payload(transaction), indent=2)
        doc.set_onload("correction_modified", str(transaction.modified))


def parse_payload(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        frappe.throw("Enter valid JSON before saving the correction.")
    if not isinstance(value, dict):
        frappe.throw("The correction payload must be a JSON object.")
    payload = value.get("payload", value)
    if not isinstance(payload, dict):
        frappe.throw("The payload must be a JSON object.")
    return value, frappe._dict(payload)


def assert_fields(doc, previous, allowed):
    current_values = doc.get_valid_dict(convert_dates_to_str=True)
    previous_values = previous.get_valid_dict(convert_dates_to_str=True)
    for field in doc.meta.fields:
        if field.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Button", "Heading"):
            continue
        current = current_values.get(field.fieldname)
        original = previous_values.get(field.fieldname)
        if field.fieldname not in allowed and current != original and not (current in (None, "") and original in (None, "")):
            frappe.throw(f"{field.label} is maintained by the POS service and cannot be edited.")
    if doc.docstatus != previous.docstatus:
        frappe.throw("Use Post / Retry to post the POS transaction.")


def lock_transaction(name):
    # Same order as the recovery worker, serializing against posting and corrections.
    identity = frappe.db.get_value("POS Accepted Transaction", name, ["branch", "customer"], as_dict=True)
    frappe.db.get_value("Branch", identity.branch, "name", for_update=True)
    frappe.db.get_value("Customer", identity.customer, "name", for_update=True)
    return frappe.get_doc("POS Accepted Transaction", name, for_update=True)


def apply_correction(transaction, payload, reason, expected=None):
    from retail import pos_settlements as service
    current = effective_payload(transaction)
    if canonical(current) == canonical(payload):
        return
    if expected and str(transaction.modified) != str(expected):
        frappe.throw("This transaction changed. Reload the document before saving your correction.")
    if transaction.pos_invoice or transaction.sales_invoice or frappe.db.exists(
            "POS Invoice", {"external_pos_reference": transaction.external_pos_reference}):
        frappe.throw("This bill is already posted. Use the bill settlement correction workflow to change accounting.")
    # Keep identity and business-day ownership stable; correction fixes bill content.
    for field in ("external_pos_reference", "company", "customer", "branch", "counter_code", "business_date", "posting_date"):
        if payload.get(field) != current.get(field):
            frappe.throw(f"A correction cannot change {field}.")
    counter = frappe.get_doc("POS Branch Counter", transaction.counter)
    _customer, rows = service.validate_payload(transaction.sync_type, payload, counter)
    allocations = [frappe.get_doc("POS Settlement Allocation", name, for_update=True)
        for name in frappe.get_all("POS Settlement Allocation", filters={"transaction": transaction.name},
            pluck="name", order_by="creation asc")]
    if any(row.applied_amount or row.get("reconciliation_reference") for row in allocations):
        frappe.throw("Settlement has already been applied. Use the bill settlement correction workflow.")
    # Retain every allocation and its versions; removed portions become zero rows.
    for index in range(max(len(rows), len(allocations))):
        values = rows[index] if index < len(rows) else dict(
            settlement_type=allocations[index].settlement_type, requested_amount=0)
        if index < len(allocations):
            allocation = allocations[index]
            allocation.update({"source_external_reference": None, **values,
                "applied_amount": 0, "unresolved_amount": values["requested_amount"],
                "status": "Accepted" if index < len(rows) else "Reconciled", "exception_reason": None})
            allocation.flags.pos_settlement_write = True
            allocation.save(ignore_permissions=True)
        else:
            common = {field: transaction.get(field) for field in (
                "company", "branch", "counter", "business_date", "customer", "cashier", "external_pos_reference")}
            service.insert(dict(common, **values, doctype="POS Settlement Allocation", transaction=transaction.name,
                applied_amount=0, unresolved_amount=values["requested_amount"], status="Accepted", created_at=now_datetime()))
    encoded = canonical(payload)
    frappe.db.set_value(transaction.doctype, transaction.name,
        {"correction_payload_json": encoded, "correction_reason": reason})
    from frappe.utils import escape_html
    transaction.add_comment("Info", text=escape_html("POS correction by {0}. Reason: {1}\nBefore: {2}\nAfter: {3}".format(
        frappe.session.user, reason, canonical(current), encoded)))


def validate_save(doc):
    require_super_admin()
    previous = doc.get_doc_before_save()
    if not previous:
        frappe.throw("POS records can only be created by the POS service.")
    payload_field = "request_json" if doc.doctype == "POS Sync Log" else "correction_payload_json"
    assert_fields(doc, previous, {payload_field, "correction_reason"})
    raw = doc.get(payload_field)
    if raw == previous.get(payload_field):
        return
    if not (doc.get("correction_reason") or "").strip():
        frappe.throw("Enter a Correction Reason before saving your edit.")
    value, payload = parse_payload(raw)
    name = transaction_name(doc)
    if name:
        transaction = lock_transaction(name)
        expected = previous.modified if doc.doctype == "POS Accepted Transaction" else (doc.get("__onload") or {}).get("correction_modified")
        # Linked forms also compare their last saved correction to the active bill.
        if not expected and doc.doctype in ("POS Settlement Allocation", "POS Settlement Exception") and previous.get(payload_field):
            if canonical(parse_payload(previous.get(payload_field))[1]) != canonical(effective_payload(transaction)):
                frappe.throw("The bill correction changed elsewhere. Reload the accepted transaction before editing.")
        apply_correction(transaction, payload, doc.correction_reason, expected)
        if doc.doctype == "POS Settlement Allocation":
            # The correction may rebuild this very allocation. Preserve those
            # service values when the outer Desk save writes the document.
            updated = frappe.get_doc(doc.doctype, doc.name)
            for field in doc.meta.fields:
                if field.fieldname not in (payload_field, "correction_reason"):
                    doc.set(field.fieldname, updated.get(field.fieldname))
    else:
        if doc.doctype != "POS Sync Log" or doc.sync_type not in SALE_TYPES:
            frappe.throw("Only POS sale and return payloads can be corrected here.")
        _, original = parse_payload(previous.request_json)
        if payload.get("external_pos_reference") != doc.external_reference or payload.get("external_pos_reference") != original.get("external_pos_reference"):
            frappe.throw("A correction cannot change the external POS reference.")
        if doc.get("operation_key") or doc.status in ("Success", "Duplicate"):
            frappe.throw("This successful operation has no accepted bill to correct.")
    if doc.doctype == "POS Sync Log":
        doc.original_request_json = previous.get("original_request_json") or previous.request_json
        # Durable operation wrappers must retain their company and counter identity.
        old_value, _ = parse_payload(previous.request_json)
        if {k: v for k, v in value.items() if k != "payload"} != {k: v for k, v in old_value.items() if k != "payload"} and "payload" in old_value:
            frappe.throw("Edit the payload inside the operation wrapper; keep its company and counter unchanged.")


@frappe.whitelist(methods=["POST"])
def retry_posting(doctype, name):
    require_super_admin()
    if doctype not in DOCTYPES:
        frappe.throw("Unsupported POS document.")
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    target = transaction_name(doc)
    from retail import pos_settlements as service
    from retail.api import pos_sync as api
    if target:
        transaction = lock_transaction(target)
        with service.recovery_context():
            if transaction.pos_invoice:
                service.resolve_transaction(transaction)
                service.refresh_day(transaction)
            else:
                payload = effective_payload(transaction)
                endpoint = api.create_pos_return_invoice if transaction.sync_type == "Return" else api.create_pos_invoice
                service.post(transaction, lambda: endpoint(payload))
        transaction.reload()
        if doctype == "POS Sync Log":
            values = {"last_attempt_at": now_datetime(), "attempt_count": (doc.attempt_count or 0) + 1}
            if transaction.status == "Reconciled":
                values.update(status="Success", error_message=None, erpnext_docname=transaction.pos_invoice)
            frappe.db.set_value(doctype, name, values)
        return {"status": transaction.status, "pos_invoice": transaction.pos_invoice,
            "sales_invoice": transaction.sales_invoice, "error": transaction.exception_reason}
    _, payload = parse_payload(doc.request_json)
    endpoint = api.create_pos_return_invoice if doc.sync_type in ("Return", "POS Return") else api.create_pos_invoice
    result = endpoint(payload)
    frappe.db.set_value(doctype, name, {"last_attempt_at": now_datetime(),
        "attempt_count": (doc.attempt_count or 0) + 1})
    if result.get("accepted"):
        frappe.db.set_value(doctype, name, {"status": "Success", "error_message": None,
            "erpnext_docname": result.get("pos_invoice_name") or result.get("return_invoice")})
    return result

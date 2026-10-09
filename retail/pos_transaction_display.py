"""Separate receipt identity and original transaction type from accounting status."""
import frappe
from frappe.utils import flt

SETTLEMENT_LABELS = {
    "Credit Sale": "Credit Sale",
    "Credit Note Issued": "Credit Note Issued",
    "Credit Note Redeemed": "Credit Note Redeemed",
    "Original Debt Reduction": "Credit Note Reduced",
}
TYPE_OPTIONS = "POS Invoice\nCredit Sale\nReturn\nCredit Note Issued\nCredit Note Redeemed\nCredit Note Reduced\nCredit Sale + Credit Note Redeemed"


def settlement_label(reference):
    transaction = frappe.db.get_value("POS Accepted Transaction", {"external_pos_reference": reference}, "name") if reference else None
    if not transaction:
        return None
    types = set(frappe.get_all("POS Settlement Allocation", filters={
        "transaction": transaction, "requested_amount": [">", 0]}, pluck="settlement_type"))
    return " + ".join(label for typ, label in SETTLEMENT_LABELS.items() if typ in types) or None


def payload_transaction_type(kind, payload):
    """Display accepted POS intent without changing the operation/retry type."""
    if kind not in ("POS Sale", "Sales Invoice", "Credit Sales Invoice", "POS Return", "Return"):
        return kind
    recorded = settlement_label(payload.get("external_pos_reference"))
    if recorded:
        return recorded
    from retail.pos_settlements import cash_payments
    if kind in ("POS Return", "Return"):
        typ = payload.get("return_settlement_type") or ("Cash Refund" if cash_payments(payload) else "Reusable Customer Credit")
        return {"Reusable Customer Credit": "Credit Note Issued", "Original Debt Reduction": "Credit Note Reduced"}.get(typ, "Return")
    redeemed = sum(flt(row.get("amount")) for row in payload.get("credit_note_redemptions") or [])
    credit = payload.get("credit_sale_amount")
    for row in payload.get("payments") or []:
        mode = row.get("mode_of_payment") or row.get("mode")
        if mode in ("Credit Note", "Credit Note Redeemed"):
            redeemed += flt(row.get("amount"))
        elif mode == "Credit Sale":
            credit = row.get("amount")
    if credit is None:
        total = payload.get("rounded_total", payload.get("grand_total"))
        paid = sum(flt(row.get("amount")) for row in cash_payments(payload))
        credit = max(0, flt(total) - paid - redeemed) if total is not None else (1 if kind == "Credit Sales Invoice" else 0)
    labels = []
    if flt(credit) > 0:
        labels.append("Credit Sale")
    if redeemed > 0:
        labels.append("Credit Note Redeemed")
    return " + ".join(labels) or "POS Invoice"


def transaction_type(doc):
    recorded = settlement_label(doc.get("external_pos_reference"))
    if recorded:
        return recorded
    if doc.get("is_return"):
        return "Return"
    total = flt(doc.get("rounded_total")) if not doc.get("disable_rounded_total") else flt(doc.get("grand_total"))
    total = total or flt(doc.get("grand_total"))
    # Initial tender is retained after later collections; outstanding balance is not.
    if round(total - flt(doc.get("paid_amount")) - flt(doc.get("write_off_amount")), 2) > 0:
        return "Credit Sale"
    return "POS Invoice"


def set_transaction_type(doc, method=None):
    doc.custom_pos_transaction_type = transaction_type(doc)


def invoice_links(result):
    doctype = result.get("doctype") or result.get("invoice_doctype")
    name = result.get("pos_invoice_name") or result.get("invoice_name") or result.get("return_invoice")
    if doctype not in ("POS Invoice", "Sales Invoice") or not name:
        return {}
    if not frappe.db.exists(doctype, name):
        return {}
    return {"linked_invoice_type": doctype, "linked_invoice": name,
        "custom_accounting_invoice": (frappe.db.get_value(doctype, name, "consolidated_invoice")
            if doctype == "POS Invoice" else name)}


def execute():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    from retail.short_codes import install
    create_custom_fields({
        "POS Invoice": [{"fieldname": "custom_pos_transaction_type", "label": "Transaction Type",
            "fieldtype": "Select", "options": TYPE_OPTIONS, "read_only": 1,
            "in_list_view": 1, "in_standard_filter": 1, "insert_after": "status", "no_copy": 1}],
        "POS Sync Log": [{"fieldname": "custom_accounting_invoice", "label": "Accounting Sales Invoice",
            "fieldtype": "Link", "options": "Sales Invoice", "read_only": 1,
            "insert_after": "linked_invoice", "in_list_view": 1},
            {"fieldname": "custom_pos_transaction_type", "label": "Sync Type",
             "fieldtype": "Data", "read_only": 1, "in_list_view": 1,
             "in_standard_filter": 1, "insert_after": "sync_type"}],
    })
    install(["Sales Invoice", "POS Invoice"])
    for row in frappe.get_all("POS Invoice", fields=["name", "external_pos_reference", "is_return", "rounded_total",
            "grand_total", "paid_amount", "write_off_amount"]):
        frappe.db.set_value("POS Invoice", row.name, "custom_pos_transaction_type",
            transaction_type(row), update_modified=False)
    for row in frappe.get_all("POS Sync Log", fields=["name", "response_json", "sync_type", "operation_key"]):
        result = frappe.parse_json(row.response_json or "{}")
        if not isinstance(result, dict):
            continue
        values = invoice_links(result)
        if values:
            # Preserve historical receipts and payloads, correcting only their display metadata.
            if values["linked_invoice_type"] == "POS Invoice" and row.sync_type in ("Sales Invoice", "Credit Sales Invoice"):
                values["sync_type"] = "POS Sale"
            frappe.db.set_value("POS Sync Log", row.name, values, update_modified=False)
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    for field in ("linked_invoice", "linked_invoice_type"):
        make_property_setter("POS Sync Log", field, "in_list_view", "1", "Check")
    for doctype, fields in {
        "POS Invoice": ["custom_pos_transaction_type", "status_field", "grand_total", "consolidated_invoice"],
        "POS Sync Log": ["custom_pos_transaction_type", "linked_invoice_type", "linked_invoice", "custom_accounting_invoice", "status"],
    }.items():
        if doctype == "POS Invoice":
            make_property_setter(doctype, "consolidated_invoice", "in_list_view", "1", "Check")
        settings = frappe.get_doc("List View Settings", doctype) if frappe.db.exists("List View Settings", doctype) else frappe.new_doc("List View Settings")
        settings.name = doctype
        settings.fields = frappe.as_json([{"fieldname": field} for field in fields])
        settings.total_fields = str(len(fields) + 2)
        settings.save(ignore_permissions=True)
    configure_settlement_types()


def configure_settlement_types():
    """Backfill display fields only; accepted facts and accounting stay intact."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    create_custom_fields({
        "POS Invoice": [{"fieldname": "custom_pos_transaction_type", "label": "Transaction Type",
            "fieldtype": "Select", "options": TYPE_OPTIONS, "read_only": 1,
            "in_list_view": 1, "in_standard_filter": 1, "insert_after": "status", "no_copy": 1}],
        "POS Sync Log": [{"fieldname": "custom_pos_transaction_type", "label": "Sync Type",
            "fieldtype": "Data", "read_only": 1, "in_list_view": 1,
            "in_standard_filter": 1, "insert_after": "sync_type"}],
    }, update=True)
    make_property_setter("POS Sync Log", "sync_type", "label", "Operation Type", "Data")
    make_property_setter("POS Sync Log", "sync_type", "in_standard_filter", "0", "Check")
    make_property_setter("POS Sync Log", "sync_type", "in_list_view", "0", "Check")
    make_property_setter("POS Invoice", "custom_pos_transaction_type", "in_list_view", "1", "Check")
    for row in frappe.get_all("POS Invoice", fields=["name", "external_pos_reference", "is_return",
            "rounded_total", "grand_total", "paid_amount", "write_off_amount"]):
        frappe.db.set_value("POS Invoice", row.name, "custom_pos_transaction_type", transaction_type(row), update_modified=False)
    for row in frappe.get_all("POS Sync Log", fields=["name", "sync_type", "request_json", "external_reference"]):
        request = frappe.parse_json(row.request_json or "{}")
        payload = request.get("payload", request) if isinstance(request, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        payload = {**payload, "external_pos_reference": payload.get("external_pos_reference") or row.external_reference}
        frappe.db.set_value("POS Sync Log", row.name, "custom_pos_transaction_type",
            payload_transaction_type(row.sync_type, payload), update_modified=False)
    for doctype in ("POS Invoice", "POS Sync Log"):
        if not frappe.db.exists("List View Settings", doctype):
            continue
        settings = frappe.get_doc("List View Settings", doctype)
        fields = frappe.parse_json(settings.fields or "[]")
        for field in fields:
            if doctype == "POS Sync Log" and field.get("fieldname") == "sync_type":
                field["fieldname"] = "custom_pos_transaction_type"
                field.pop("label", None)
        if not any(field.get("fieldname") == "custom_pos_transaction_type" for field in fields):
            fields.insert(1 if fields else 0, {"fieldname": "custom_pos_transaction_type"})
            settings.total_fields = str(min(10, max(4, len(fields) + 1)))
        settings.fields = frappe.as_json(fields)
        settings.save(ignore_permissions=True)
    frappe.clear_cache()

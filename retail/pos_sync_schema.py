"""Ensure POS posting fields exist on fresh installs and migrated sites."""
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_completed_payload_field():
    create_custom_fields({"POS Invoice": [{
        "fieldname": "custom_pos_completed_payload", "label": "Completed POS Payload",
        "fieldtype": "Code", "options": "JSON", "read_only": 1, "hidden": 1,
        "no_copy": 1, "insert_after": "external_pos_reference",
    }]}, update=True)


def ensure_settlement_fields():
    fields = [("credit_sales", "Credit Sales"), ("credit_notes_issued", "Credit Note Issued"),
              ("credit_notes_redeemed", "Credit Note Redeemed"),
              ("credit_notes_applied", "Credit Note Applied"),
              ("credit_notes_unresolved", "Credit Note Unresolved")]
    definitions = {doctype: [{
        "fieldname": "pos_" + field, "label": label, "fieldtype": "Currency",
        "read_only": 1, "allow_on_submit": 1,
    } for field, label in fields] for doctype in (
        "POS Branch Day Closing", "POS Cashier Shift", "POS Closing Entry")}
    definitions["POS Branch Day Closing"].append({
        "fieldname": "pos_settlement_totals", "label": "POS Settlement Totals",
        "fieldtype": "Long Text", "read_only": 1, "allow_on_submit": 1,
        "insert_after": "payment_totals",
    })
    create_custom_fields(definitions)


def install():
    ensure_completed_payload_field()
    ensure_settlement_fields()


def validate():
    """Read-only installation gate: require posting fields before any migration."""
    import frappe

    expected = {"POS Invoice": ["external_pos_reference", "custom_pos_completed_payload"]}
    for doctype in ("POS Cashier Shift", "POS Closing Entry", "POS Branch Day Closing"):
        expected[doctype] = ["pos_" + suffix for suffix in (
            "credit_sales", "credit_notes_issued", "credit_notes_redeemed",
            "credit_notes_applied", "credit_notes_unresolved")]
    expected["POS Branch Day Closing"].append("pos_settlement_totals")
    missing = [f"{doctype}.{field}" for doctype, fields in expected.items()
               for field in fields if not frappe.db.has_column(doctype, field)]
    if missing:
        raise RuntimeError("Missing POS posting schema: " + ", ".join(missing))
    return {"pos_posting_schema": "OK"}

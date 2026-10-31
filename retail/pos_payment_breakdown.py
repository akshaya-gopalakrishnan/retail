"""Read-only receipt settlement display; never add native payment entries."""
import frappe
from frappe.utils import flt


def onload(doc, method=None):
    doc.check_permission("read")
    filters = {"company": doc.company, "customer": doc.customer}
    if doc.doctype == "POS Invoice":
        reference = doc.get("external_pos_reference")
        if not reference:
            doc.set_onload("retail_payment_settlements", [])
            return
        filters["external_pos_reference"] = reference
    else:
        filters["sales_invoice"] = doc.name
    transactions = frappe.get_all("POS Accepted Transaction", filters=filters, pluck="name")
    rows = frappe.get_all("POS Settlement Allocation", filters={
        "transaction": ["in", transactions], "requested_amount": [">", 0],
        "settlement_type": ["in", ["Credit Note Redeemed", "Credit Note Issued",
                                    "Credit Sale", "Original Debt Reduction"]],
    }, fields=["settlement_type", "requested_amount", "applied_amount", "unresolved_amount",
               "source_external_reference", "external_pos_reference", "status"],
        order_by="creation asc, name asc") if transactions else []
    doc.set_onload("retail_payment_settlements", [dict(
        mode_of_payment=row.settlement_type,
        amount=flt(row.requested_amount),
        applied_amount=flt(row.applied_amount),
        unresolved_amount=flt(row.unresolved_amount),
        reference_no=(row.source_external_reference if row.settlement_type == "Credit Note Redeemed"
                      else row.external_pos_reference),
        status=row.status,
    ) for row in rows])


def execute():
    """Remove the superseded standalone display; native payment grid renders it."""
    for doctype in ("POS Invoice", "Sales Invoice"):
        for fieldname in ("custom_pos_payment_breakdown", "custom_pos_payment_breakdown_section"):
            name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname})
            if name:
                frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
        frappe.clear_cache(doctype=doctype)

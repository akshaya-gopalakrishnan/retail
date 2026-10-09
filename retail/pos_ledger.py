"""Resolve a POS receipt to its actual accounting voucher for ledger navigation."""

import frappe


@frappe.whitelist()
def get_ledger_context(pos_invoice):
    receipt = frappe.get_doc("POS Invoice", pos_invoice)
    receipt.check_permission("read")
    if not receipt.consolidated_invoice:
        return {"posted": False, "cancelled": receipt.docstatus == 2}

    invoice = frappe.get_doc("Sales Invoice", receipt.consolidated_invoice)
    invoice.check_permission("read")
    if invoice.docstatus == 0:
        return {"posted": False, "cancelled": receipt.docstatus == 2}

    return {
        "posted": True,
        "voucher_no": invoice.name,
        "company": invoice.company,
        "posting_date": str(invoice.posting_date),
        "cancelled": invoice.docstatus == 2,
        "update_stock": bool(invoice.update_stock),
        "combined": bool(frappe.db.exists("POS Invoice", {
            "consolidated_invoice": invoice.name,
            "name": ["!=", receipt.name],
        })),
    }

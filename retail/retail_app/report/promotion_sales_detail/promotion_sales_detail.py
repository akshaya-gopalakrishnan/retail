import frappe
from retail.promotions.history import columns, report_rows, execute_summary


@frappe.whitelist()
def get_promotions(txt=""):
    """Offer readable promotion records, including inactive historical rules."""
    from retail.promotions.history import TYPES

    names = set()
    for doctype in TYPES:
        if not frappe.has_permission(doctype, "read"):
            continue
        names.update(frappe.get_list(
            doctype,
            filters={"name": ["like", "%" + txt + "%"]},
            pluck="name",
            order_by="name asc",
            page_length=50,
        ))
    return sorted(names)


def execute(filters=None):
    return columns(), list(report_rows(frappe._dict(filters or {}))), 'Amounts are POS-reported, excluding VAT. Schedule checks do not certify item eligibility or discount calculations.'

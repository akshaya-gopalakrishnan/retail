"""Show shift business dates beside the session's actual start/end timestamps."""
import frappe
from frappe.utils import getdate


def execute():
    from retail.pos_list_settings import COLUMNS, configure_columns
    frappe.reload_doc("retail_app", "doctype", "pos_counter_session")
    for session in frappe.get_all("POS Counter Session", fields=["name", "cashier_shift", "business_date"]):
        if session.business_date:
            continue
        shift = frappe.db.get_value("POS Cashier Shift", session.cashier_shift,
            ["business_date", "opening_time"], as_dict=True)
        if shift:
            frappe.db.set_value("POS Counter Session", session.name, "business_date",
                shift.business_date or getdate(shift.opening_time), update_modified=False)
    configure_columns("POS Counter Session", COLUMNS["POS Counter Session"])
    frappe.clear_cache(doctype="POS Counter Session")

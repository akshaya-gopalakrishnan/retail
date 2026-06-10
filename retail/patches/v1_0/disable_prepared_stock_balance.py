import frappe


def execute():
    if not frappe.db.exists("Report", "Stock Balance"):
        return

    if frappe.db.get_value("Report", "Stock Balance", "prepared_report"):
        frappe.db.set_value(
            "Report",
            "Stock Balance",
            "prepared_report",
            0,
            update_modified=False,
        )

    frappe.clear_cache(doctype="Report")

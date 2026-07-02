import frappe


def execute():
	for doctype in ("Sales Invoice", "Sales Order", "Delivery Note", "Payment Entry"):
		fieldname = f"{doctype}-sales_channel"
		if frappe.db.exists("Custom Field", fieldname):
			frappe.delete_doc("Custom Field", fieldname, force=True, ignore_permissions=True)
		frappe.clear_cache(doctype=doctype)

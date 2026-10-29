"""Read-only previews for the native Batch Quick Entry dialog."""

import frappe


@frappe.whitelist()
def get_item_defaults(item):
	frappe.has_permission("Batch", "create", throw=True)
	item_doc = frappe.get_doc("Item", item)
	item_doc.check_permission("read")
	return {"stock_uom": item_doc.stock_uom}

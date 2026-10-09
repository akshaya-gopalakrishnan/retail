"""Map existing packings through the normal Item save and Item Price hooks."""

import frappe


def execute():
	frappe.reload_doc("retail_app", "doctype", "retail_packing_detail")
	items = frappe.get_all("Retail Packing Detail", filters={"parenttype": "Item"},
		pluck="parent", distinct=True)
	for item_code in items:
		# No per-item commits: ambiguous data aborts migration rather than guessing.
		frappe.get_doc("Item", item_code).save(ignore_permissions=True)

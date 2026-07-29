import frappe


def execute():
	if not frappe.db.exists("DocType", "Retail Packing Detail"):
		return
	if not frappe.db.has_column("Retail Packing Detail", "is_fast_plu_item"):
		return

	frappe.db.sql(
		"""
		update `tabRetail Packing Detail`
		set is_fast_plu_item = 0
		where is_fast_plu_item is null
		"""
	)

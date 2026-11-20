"""Retain the selected packing identity on Sales Order rows."""
import frappe


def apply_packing_identity(doc, method=None):
	for row in doc.items:
		packing_id = row.get("custom_packing_detail")
		if not packing_id:
			continue
		packing = frappe.db.get_value("Retail Packing Detail", {
			"name": packing_id, "parent": row.item_code, "parenttype": "Item", "uom": row.uom,
		}, ["packing_name", "barcode"], as_dict=True)
		if not packing:
			row.custom_packing_detail = ""
			continue
		row.item_name = packing.packing_name or row.item_name
		row.custom_item_barcode = packing.barcode or ""

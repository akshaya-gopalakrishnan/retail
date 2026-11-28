"""Index the barcode and price columns item entry looks up by value."""
import frappe


LOOKUPS = (
	("Item", "custom_barcode"),
	("Item Price", "custom_barcode"),
	("Retail Packing Detail", "barcode"),
)


def _indexed(doctype, column):
	return bool(frappe.db.sql(
		"""
		select 1 from information_schema.statistics
		where table_schema = database() and table_name = %s
			and column_name = %s and seq_in_index = 1
		limit 1
		""",
		(f"tab{doctype}", column),
	))


def execute():
	for doctype, field in LOOKUPS:
		if not frappe.db.has_column(doctype, field):
			continue
		if doctype == "Retail Packing Detail":
			frappe.db.set_value("DocField", {"parent": doctype, "fieldname": field},
				"search_index", 1, update_modified=False)
		elif frappe.db.exists("Custom Field", f"{doctype}-{field}"):
			frappe.db.set_value("Custom Field", f"{doctype}-{field}", "search_index", 1, update_modified=False)
		if not _indexed(doctype, field):
			frappe.db.add_index(doctype, [field])
	if all(frappe.db.has_column("Item Price", field) for field in ("item_code", "price_list", "uom")):
		frappe.db.add_index("Item Price", ["item_code", "price_list", "uom"])

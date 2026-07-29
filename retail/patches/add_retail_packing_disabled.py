import frappe


PACKING_GRID_COLUMNS = [
	{"fieldname": "packing_name", "columns": 2},
	{"fieldname": "barcode", "columns": 1},
	{"fieldname": "uom", "columns": 1},
	{"fieldname": "conversion_factor", "columns": 1},
	{"fieldname": "purchase_net_rate", "columns": 1},
	{"fieldname": "purchase_gross_rate", "columns": 1},
	{"fieldname": "selling_net_rate", "columns": 1},
	{"fieldname": "selling_gross_rate", "columns": 1},
	{"fieldname": "is_fast_plu_item", "columns": 1},
	{"fieldname": "disabled", "columns": 1},
]


def execute():
	if not frappe.db.exists("DocType", "Retail Packing Detail"):
		return
	if not frappe.db.has_column("Retail Packing Detail", "disabled"):
		return

	frappe.db.sql(
		"""
		update `tabRetail Packing Detail`
		set disabled = 0
		where disabled is null
		"""
	)

	defaults = {"Item": {"Retail Packing Detail": PACKING_GRID_COLUMNS}}
	for user in frappe.get_all("User", filters={"enabled": 1}, pluck="name"):
		if user != "Guest":
			frappe.get_attr("retail.grid_view_settings.apply_default_grid_view_settings_for_user")(
				user,
				defaults=defaults,
				overwrite=True,
			)

	frappe.clear_cache(doctype="Retail Packing Detail")

import frappe


DOCFIELD_LABELS = {
	"purchase_rate": "Purchase Rate",
	"selling_rate": "Selling Rate",
}

CUSTOM_FIELD_LABELS = {
	"purchase_net_rate": "Purchase Rate Excl. VAT",
	"purchase_gross_rate": "Purchase Rate Incl. VAT",
	"selling_net_rate": "Selling Rate Excl. VAT",
	"selling_gross_rate": "Selling Rate Incl. VAT",
}

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
]


def execute():
	for fieldname, label in DOCFIELD_LABELS.items():
		frappe.db.set_value(
			"DocField",
			{"parent": "Retail Packing Detail", "fieldname": fieldname},
			"label",
			label,
			update_modified=False,
		)

	for fieldname, label in CUSTOM_FIELD_LABELS.items():
		name = f"Retail Packing Detail-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			frappe.db.set_value("Custom Field", name, "label", label, update_modified=False)

	defaults = {"Item": {"Retail Packing Detail": PACKING_GRID_COLUMNS}}
	for user in frappe.get_all("User", filters={"enabled": 1}, pluck="name"):
		if user != "Guest":
			frappe.get_attr("retail.grid_view_settings.apply_default_grid_view_settings_for_user")(
				user,
				defaults=defaults,
				overwrite=True,
			)

	frappe.clear_cache(doctype="Retail Packing Detail")

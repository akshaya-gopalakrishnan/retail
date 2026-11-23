"""Add the Supplier Incoterm selection below Is Transporter."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	# Keep the code as the Link value and show the meaning below it in search.
	make_property_setter(
		"Incoterm", None, "show_title_field_in_link", 0, "Check", for_doctype=True
	)
	create_custom_fields({
		"Supplier": [{
			"fieldname": "custom_incoterm",
			"label": "Incoterm",
			"fieldtype": "Link",
			"options": "Incoterm",
			"insert_after": "is_transporter",
			"in_list_view": 1,
			"in_standard_filter": 1,
		}],
	})
	# Allow room for the existing Supplier columns as well as Incoterm.
	if not frappe.db.exists("List View Settings", "Supplier"):
		frappe.get_doc({
			"doctype": "List View Settings",
			"name": "Supplier",
			"total_fields": "6",
		}).insert(ignore_permissions=True)
	settings = frappe.get_doc("List View Settings", "Supplier")
	fields = frappe.parse_json(settings.fields) if settings.fields else [
		{"fieldname": "status_field"},
		{"fieldname": "supplier_group"},
		{"fieldname": "tax_id"},
	]
	fields = [field for field in fields if field["fieldname"] != "custom_incoterm"]
	if not any(field["fieldname"] == "tax_id" for field in fields):
		fields.append({"fieldname": "tax_id"})
	index = next(i for i, field in enumerate(fields) if field["fieldname"] == "tax_id")
	fields.insert(index + 1, {"fieldname": "custom_incoterm"})
	settings.fields = frappe.as_json(fields)
	settings.total_fields = str(max(int(settings.total_fields or 6), len(fields) + 2))
	settings.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Supplier")

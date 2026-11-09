"""Show the supplier in the standard Item Defaults grid."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	# All four Link fields must fit within the grid's ten available columns.
	for fieldname, columns in (
		("company", 3),
		("default_warehouse", 2),
		("default_price_list", 2),
		("default_supplier", 3),
	):
		make_property_setter(
			"Item Default", fieldname, "columns", columns, "Int",
			validate_fields_for_doctype=False,
		)
	make_property_setter(
		"Item Default", "default_supplier", "in_list_view", 1, "Check",
		validate_fields_for_doctype=False,
	)
	frappe.clear_cache(doctype="Item Default")

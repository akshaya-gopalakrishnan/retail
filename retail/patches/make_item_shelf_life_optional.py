"""Allow expiry-tracked Items without a default shelf-life calculation."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	make_property_setter(
		"Item", "shelf_life_in_days", "mandatory_depends_on", "", "Data",
		validate_fields_for_doctype=False,
	)
	frappe.clear_cache(doctype="Item")

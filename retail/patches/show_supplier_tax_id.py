"""Show Tax ID in the Supplier list and its standard filter bar."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	for property_name in ("in_list_view", "in_standard_filter"):
		make_property_setter(
			"Supplier", "tax_id", property_name, 1, "Check",
			validate_fields_for_doctype=False,
		)
	frappe.clear_cache(doctype="Supplier")

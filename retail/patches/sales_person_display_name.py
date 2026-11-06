"""Add repeatable display names without renaming existing Sales Persons."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	create_custom_fields({"Sales Person": [{
		"fieldname": "custom_display_name", "label": "Display Name", "fieldtype": "Data",
		"insert_after": "name_and_employee_id", "in_list_view": 1,
		"allow_in_quick_entry": 1,
		"description": "",
	}]}, ignore_validate=True)
	make_property_setter(
		"Sales Person", "sales_person_name", "read_only", 1, "Check",
		validate_fields_for_doctype=False,
	)
	make_property_setter(
		"Sales Person", None, "title_field", "custom_display_name", "Data",
		for_doctype=True, validate_fields_for_doctype=False,
	)
	make_property_setter(
		"Sales Person", "sales_person_name", "in_list_view", 0, "Check",
		validate_fields_for_doctype=False,
	)
	# Legacy records already have a human name; preserve their stored identity.
	frappe.db.sql("""
		UPDATE `tabSales Person`
		SET custom_display_name = sales_person_name
		WHERE COALESCE(custom_display_name, '') = ''
	""")
	frappe.clear_cache(doctype="Sales Person")

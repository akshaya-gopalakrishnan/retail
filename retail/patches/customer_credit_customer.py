"""Add the manually selected credit-customer flag to Customer creation."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({"Customer": [{
		"fieldname": "custom_is_credit_customer",
		"label": "Is Credit Customer",
		"fieldtype": "Check",
		"insert_after": "customer_name",
		"default": "0",
		"allow_in_quick_entry": 1,
	}]})

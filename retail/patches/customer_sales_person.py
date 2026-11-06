"""Add a single Sales Person assignment to the Customer Sales Team tab."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({"Customer": [{
		"fieldname": "custom_sales_person",
		"label": "Sales Person",
		"fieldtype": "Link",
		"options": "Sales Person",
		"insert_after": "sales_team_tab",
	}]})

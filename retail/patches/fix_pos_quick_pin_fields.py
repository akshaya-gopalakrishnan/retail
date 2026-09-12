import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "pos_quick_pin",
					"fieldtype": "Data",
					"length": 4,
				}
			],
			"User": [
				{
					"fieldname": "pos_quick_pin",
					"fieldtype": "Data",
					"length": 4,
				}
			],
		},
		ignore_validate=True,
		update=True,
	)
	frappe.db.updatedb("Employee")
	frappe.db.updatedb("User")
	frappe.clear_cache(doctype="Employee")
	frappe.clear_cache(doctype="User")
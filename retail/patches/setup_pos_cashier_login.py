import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "pos_login_section",
					"label": "POS Login",
					"fieldtype": "Section Break",
					"insert_after": "user_id",
					"collapsible": 1,
				},
				{
					"fieldname": "pos_login_enabled",
					"label": "Allow POS Login",
					"fieldtype": "Check",
					"default": "1",
					"insert_after": "pos_login_section",
				},
				{
					"fieldname": "pos_login_id",
					"label": "POS Login ID",
					"fieldtype": "Int",
					"insert_after": "pos_login_enabled",
					"description": "",
				},
				{
					"fieldname": "pos_login_user",
					"label": "POS Login User",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "pos_login_id",
					"description": "",
				},
				{
					"fieldname": "pos_quick_pin",
					"label": "Set POS Quick PIN",
					"fieldtype": "Data",
					"length": 4,
					"insert_after": "pos_login_user",
					"description": "",
					"no_copy": 1,
				},
				{
					"fieldname": "pos_quick_pin_salt",
					"label": "POS Quick PIN Salt",
					"fieldtype": "Data",
					"insert_after": "pos_quick_pin",
					"hidden": 1,
					"read_only": 1,
					"no_copy": 1,
				},
				{
					"fieldname": "pos_quick_pin_hash",
					"label": "POS Quick PIN Hash",
					"fieldtype": "Data",
					"insert_after": "pos_quick_pin_salt",
					"hidden": 1,
					"read_only": 1,
					"no_copy": 1,
				},
			],
			"User": [
				{
					"fieldname": "pos_login_section",
					"label": "POS Login",
					"fieldtype": "Section Break",
					"insert_after": "roles",
					"collapsible": 1,
				},
				{
					"fieldname": "pos_login_enabled",
					"label": "Allow POS Login",
					"fieldtype": "Check",
					"default": "1",
					"insert_after": "pos_login_section",
				},
				{
					"fieldname": "pos_cashier_employee",
					"label": "POS Cashier Employee",
					"fieldtype": "Link",
					"options": "Employee",
					"insert_after": "pos_login_enabled",
					"description": "",
				},
				{
					"fieldname": "pos_quick_pin",
					"hidden": 1,
					"label": "Set POS Quick PIN",
					"fieldtype": "Data",
					"length": 4,
					"insert_after": "pos_cashier_employee",
					"description": "",
					"no_copy": 1,
				},
			]
		},
		ignore_validate=True,
		update=True,
	)
	frappe.db.updatedb("Employee")
	frappe.db.updatedb("User")
	frappe.clear_cache(doctype="Employee")
	frappe.clear_cache(doctype="User")

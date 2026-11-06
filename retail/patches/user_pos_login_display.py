"""Show User POS settings only for an already linked Employee."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({"User": [
		{
			"fieldname": "pos_login_section", "label": "POS Login",
			"fieldtype": "Section Break", "insert_after": "roles", "collapsible": 1,
			"depends_on": "eval:!!doc.pos_cashier_employee",
		},
		{
			"fieldname": "pos_login_id", "label": "POS Login ID", "fieldtype": "Int",
			"insert_after": "pos_cashier_employee", "read_only": 1, "no_copy": 1,
		},
	]})
	# Leave the Employee link visible as context, but assign it on Employee.
	frappe.db.set_value("Custom Field", "User-pos_cashier_employee", "read_only", 1)
	# PIN entry belongs to Employee POS Login; retain the field for compatibility.
	frappe.db.set_value("Custom Field", "User-pos_quick_pin", "hidden", 1)
	for dt, fields in {
		"User": ("pos_cashier_employee", "pos_quick_pin"),
		"Employee": ("pos_login_id", "pos_login_user", "pos_quick_pin", "pos_operator_privilege"),
	}.items():
		for fieldname in fields:
			name = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
			if name:
				frappe.db.set_value("Custom Field", name, "description", "")
		frappe.clear_cache(doctype=dt)

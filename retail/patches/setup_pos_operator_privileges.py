import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	from retail.patches.setup_pos_cashier_login import execute as setup_login

	setup_login()
	create_custom_fields({"Employee": [
		{"fieldname": "pos_settings_tab", "label": "POS Settings", "fieldtype": "Tab Break", "insert_after": "old_parent"},
		{"fieldname": "pos_login_section", "label": "POS Login", "fieldtype": "Section Break", "insert_after": "pos_settings_tab", "collapsible": 0},
		{"fieldname": "pos_privileges_section", "label": "POS Operator Privileges", "fieldtype": "Section Break", "insert_after": "pos_quick_pin_hash"},
		{"fieldname": "pos_operator_privilege", "label": "POS Operator Privilege", "fieldtype": "Link", "options": "POS Operator Privilege", "insert_after": "pos_privileges_section", "no_copy": 1, "description": "Select a shared permission profile. Only System Managers can change this assignment. No profile means no POS actions are allowed."},
		{"fieldname": "pos_privileges_preview", "label": "Allowed POS Actions", "fieldtype": "HTML", "insert_after": "pos_operator_privilege"},
	]}, update=True)
	frappe.clear_cache(doctype="Employee")

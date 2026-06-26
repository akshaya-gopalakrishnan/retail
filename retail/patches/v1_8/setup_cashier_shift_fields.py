import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	frappe.flags.in_patch = True
	create_custom_fields(get_custom_fields(), ignore_validate=True, update=True)
	for doctype in ("POS Invoice", "Sales Invoice", "Payment Entry", "POS Opening Entry", "POS Closing Entry"):
		frappe.clear_cache(doctype=doctype)


def get_custom_fields():
	common_cashier_fields = [
		{
			"fieldname": "pos_cashier_employee",
			"label": "POS Cashier Employee",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "pos_cashier",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "pos_cashier_shift",
			"label": "POS Cashier Shift",
			"fieldtype": "Link",
			"options": "POS Cashier Shift",
			"insert_after": "pos_cashier_employee",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "pos_counter_session",
			"label": "POS Counter Session",
			"fieldtype": "Link",
			"options": "POS Counter Session",
			"insert_after": "pos_cashier_shift",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
	]

	payment_fields = [
		{
			"fieldname": "pos_cashier_employee",
			"label": "POS Cashier Employee",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "pos_terminal_id",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "pos_cashier_shift",
			"label": "POS Cashier Shift",
			"fieldtype": "Link",
			"options": "POS Cashier Shift",
			"insert_after": "pos_cashier_employee",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "pos_counter_session",
			"label": "POS Counter Session",
			"fieldtype": "Link",
			"options": "POS Counter Session",
			"insert_after": "pos_cashier_shift",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
	]

	opening_closing_fields = [
		{
			"fieldname": "offline_pos_section",
			"label": "Offline POS",
			"fieldtype": "Section Break",
			"insert_after": "status",
			"collapsible": 1,
			"allow_on_submit": 1,
		},
		{
			"fieldname": "pos_branch_counter",
			"label": "POS Branch Counter",
			"fieldtype": "Link",
			"options": "POS Branch Counter",
			"insert_after": "offline_pos_section",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "pos_cashier_employee",
			"label": "POS Cashier Employee",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "pos_branch_counter",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "pos_cashier_shift",
			"label": "POS Cashier Shift",
			"fieldtype": "Link",
			"options": "POS Cashier Shift",
			"insert_after": "pos_cashier_employee",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "pos_counter_session",
			"label": "POS Counter Session",
			"fieldtype": "Link",
			"options": "POS Counter Session",
			"insert_after": "pos_cashier_shift",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
	]

	return {
		"POS Invoice": common_cashier_fields,
		"Sales Invoice": common_cashier_fields,
		"Payment Entry": payment_fields,
		"POS Opening Entry": opening_closing_fields,
		"POS Closing Entry": opening_closing_fields,
	}

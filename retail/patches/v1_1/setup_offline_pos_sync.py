import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	frappe.flags.in_patch = True
	ensure_role()
	create_custom_fields(get_custom_fields(), ignore_validate=True, update=True)
	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Payment Entry")


def ensure_role():
	if not frappe.db.exists("Role", "POS Integration User"):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": "POS Integration User",
				"desk_access": 0,
				"is_custom": 1,
			}
		).insert(ignore_permissions=True)


def get_custom_fields():
	sales_invoice_fields = [
		{
			"fieldname": "pos_sync_section",
			"label": "Offline POS Sync",
			"fieldtype": "Section Break",
			"insert_after": "cost_center",
			"collapsible": 0,
			"allow_on_submit": 1,
		},
		{
			"fieldname": "external_pos_reference",
			"label": "External POS Reference",
			"fieldtype": "Data",
			"insert_after": "pos_sync_section",
			"in_list_view": 0,
			"in_standard_filter": 0,
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_bill_no",
			"label": "POS Bill No",
			"fieldtype": "Data",
			"insert_after": "external_pos_reference",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_branch",
			"label": "POS Branch",
			"fieldtype": "Link",
			"options": "Branch",
			"insert_after": "pos_bill_no",
			"in_standard_filter": 0,
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_counter",
			"label": "POS Counter",
			"fieldtype": "Link",
			"options": "POS Branch Counter",
			"insert_after": "pos_branch",
			"in_standard_filter": 0,
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_terminal_id",
			"label": "POS Terminal ID",
			"fieldtype": "Data",
			"insert_after": "pos_counter",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_column_break",
			"fieldtype": "Column Break",
			"insert_after": "pos_terminal_id",
		},
		{
			"fieldname": "pos_shift_no",
			"label": "POS Shift No",
			"fieldtype": "Data",
			"insert_after": "pos_column_break",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_cashier",
			"label": "POS Cashier",
			"fieldtype": "Data",
			"insert_after": "pos_shift_no",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_sync_source",
			"label": "POS Sync Source",
			"fieldtype": "Data",
			"insert_after": "pos_cashier",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_sync_datetime",
			"label": "POS Sync Datetime",
			"fieldtype": "Datetime",
			"insert_after": "pos_sync_source",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_local_created_at",
			"label": "POS Local Created At",
			"fieldtype": "Datetime",
			"insert_after": "pos_sync_datetime",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_original_reference",
			"label": "POS Original Reference",
			"fieldtype": "Data",
			"insert_after": "pos_local_created_at",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
	]

	payment_entry_fields = [
		{
			"fieldname": "pos_sync_section",
			"label": "Offline POS Sync",
			"fieldtype": "Section Break",
			"insert_after": "reference_date",
			"collapsible": 1,
			"allow_on_submit": 1,
		},
		{
			"fieldname": "external_pos_reference",
			"label": "External POS Reference",
			"fieldtype": "Data",
			"insert_after": "pos_sync_section",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_branch",
			"label": "POS Branch",
			"fieldtype": "Link",
			"options": "Branch",
			"insert_after": "external_pos_reference",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_counter",
			"label": "POS Counter",
			"fieldtype": "Link",
			"options": "POS Branch Counter",
			"insert_after": "pos_branch",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_terminal_id",
			"label": "POS Terminal ID",
			"fieldtype": "Data",
			"insert_after": "pos_counter",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_sync_source",
			"label": "POS Sync Source",
			"fieldtype": "Data",
			"insert_after": "pos_terminal_id",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "pos_sync_datetime",
			"label": "POS Sync Datetime",
			"fieldtype": "Datetime",
			"insert_after": "pos_sync_source",
			"allow_on_submit": 1,
			"read_only": 1,
			"no_copy": 1,
		},
	]

	pos_invoice_fields = [field.copy() for field in sales_invoice_fields]
	for field in pos_invoice_fields:
		if field.get("fieldname") == "pos_sync_section":
			field["insert_after"] = "pos_profile"
		if field.get("fieldname") == "pos_counter":
			field["options"] = "POS Branch Counter"

	return {
		"Sales Invoice": sales_invoice_fields,
		"POS Invoice": pos_invoice_fields,
		"Payment Entry": payment_entry_fields,
	}

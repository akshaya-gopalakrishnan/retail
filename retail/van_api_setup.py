"""Additive schema for the mobile Van Sales API; never changes business records."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_van_api_fields():
	create_custom_fields({
		"Van Fleet": [
			{"fieldname": "custom_van_api_section", "label": "Mobile Sales Settings", "fieldtype": "Section Break"},
			{"fieldname": "custom_selling_price_list", "label": "Selling Price List", "fieldtype": "Link", "options": "Price List", "insert_after": "custom_van_api_section"},
			{"fieldname": "custom_sales_taxes_and_charges", "label": "Sales Taxes and Charges", "fieldtype": "Link", "options": "Sales Taxes and Charges Template", "insert_after": "custom_selling_price_list"},
			{"fieldname": "custom_cost_center", "label": "Cost Center", "fieldtype": "Link", "options": "Cost Center", "insert_after": "custom_sales_taxes_and_charges"},
			{"fieldname": "custom_source_warehouse", "label": "Loading / Return Warehouse", "fieldtype": "Link", "options": "Warehouse", "insert_after": "rc_number"},
		],
		"Customer": [
			{"fieldname": "custom_van_driver", "label": "Van Driver", "fieldtype": "Link", "options": "Driver", "insert_after": "custom_is_van_customer"},
			{"fieldname": "custom_van_external_id", "label": "Van App Customer ID", "fieldtype": "Data", "read_only": 1, "unique": 1, "no_copy": 1, "insert_after": "custom_van_driver"},
		],
		"Van Session": [
			{"fieldname": "custom_activity_status", "label": "Mobile Activity", "fieldtype": "Select", "options": "Active\nBreak", "default": "Active", "allow_on_submit": 1},
			{"fieldname": "custom_activity_time", "label": "Mobile Activity Time", "fieldtype": "Datetime", "allow_on_submit": 1},
			{"fieldname": "custom_app_open_time", "label": "App Opening Time", "fieldtype": "Datetime", "allow_on_submit": 1},
			{"fieldname": "custom_app_close_time", "label": "App Closing Time", "fieldtype": "Datetime", "allow_on_submit": 1},
			{"fieldname": "custom_collection_details", "label": "App Closing Collections", "fieldtype": "Long Text", "allow_on_submit": 1, "read_only": 1},
		],
	}, update=True)


def install():
	"""Targeted installation for an existing site, without running unrelated migrations."""
	for name in ("van_api_request", "van_expense_type", "van_expense"):
		frappe.reload_doc("retail_app", "doctype", name, force=True)
	ensure_van_api_fields()
	frappe.clear_cache()
	return "Van Sales API schema installed."

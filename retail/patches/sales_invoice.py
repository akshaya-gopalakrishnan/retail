"""All Sales Invoice metadata customisations in one patch module."""

import frappe

from retail.domains.sales.counter import ensure_counter_display_field
from retail.domains.sales.invoice_totals import ensure_sales_invoice_retail_totals_fields


SALES_INVOICE_POS_FIELDS = (
	"pos_sync_section",
	"external_pos_reference",
	"pos_bill_no",
	"pos_branch",
	"pos_counter",
	"pos_terminal_id",
	"pos_column_break",
	"pos_shift_no",
	"pos_cashier",
	"pos_cashier_employee",
	"pos_cashier_shift",
	"pos_counter_session",
	"pos_sync_source",
	"pos_sync_datetime",
	"pos_local_created_at",
	"pos_original_reference",
)


def execute():
	ensure_sales_invoice_fields()


def ensure_sales_invoice_fields():
	ensure_counter_display_field()
	_remove_pos_sync_fields()
	_hide_counter_link_field()
	ensure_sales_invoice_retail_totals_fields()
	frappe.clear_cache(doctype="Sales Invoice")


def _remove_pos_sync_fields():
	for fieldname in SALES_INVOICE_POS_FIELDS:
		name = f"Sales Invoice-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)


def _hide_counter_link_field():
	if frappe.db.exists("Custom Field", "Sales Invoice-custom_counter"):
		frappe.db.set_value(
			"Custom Field",
			"Sales Invoice-custom_counter",
			{
				"hidden": 1,
				"in_list_view": 0,
				"in_standard_filter": 0,
				"report_hide": 1,
				"no_copy": 1,
			},
			update_modified=False,
		)

	if frappe.db.exists("Property Setter", "Sales Invoice-custom_counter-in_list_view"):
		frappe.delete_doc(
			"Property Setter",
			"Sales Invoice-custom_counter-in_list_view",
			force=True,
			ignore_permissions=True,
		)

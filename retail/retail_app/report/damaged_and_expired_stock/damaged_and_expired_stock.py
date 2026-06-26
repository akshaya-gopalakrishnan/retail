import frappe
from frappe import _
from frappe.utils import flt

from retail.retail_app.report.stock_movement_utils import (
	get_stock_movements,
	is_damage_movement,
	is_expiry_movement,
)


REPORT_NAME = "Damaged and Expired Stock"
LEGACY_REPORT_NAME = "Damaged / Expired Stock"


def execute(filters=None):
	data = []
	for row in get_stock_movements(filters):
		if not row.qty_out:
			continue

		is_expired = is_expiry_movement(row) or (
			row.expiry_date and row.voucher_type == "Stock Entry"
		)
		if not (is_expired or is_damage_movement(row)):
			continue

		row.category = _("Expired") if is_expired else _("Damaged")
		row.loss_value = abs(flt(row.stock_value_difference))
		data.append(row)

	return get_columns(), data


def ensure_report():
	"""Register the report and rename the invalid legacy report if present."""
	if frappe.db.exists("Report", LEGACY_REPORT_NAME):
		if not frappe.db.exists("Report", REPORT_NAME):
			frappe.rename_doc("Report", LEGACY_REPORT_NAME, REPORT_NAME, force=True, ignore_permissions=True)
		else:
			frappe.delete_doc("Report", LEGACY_REPORT_NAME, force=True, ignore_permissions=True)

	if frappe.db.exists("Report", REPORT_NAME):
		frappe.db.set_value(
			"Report",
			REPORT_NAME,
			{"report_name": REPORT_NAME, "report_type": "Script Report", "ref_doctype": "Stock Ledger Entry"},
			update_modified=False,
		)
		return

	frappe.get_doc(
		{
			"doctype": "Report",
			"name": REPORT_NAME,
			"report_name": REPORT_NAME,
			"module": "Retail-app",
			"ref_doctype": "Stock Ledger Entry",
			"report_type": "Script Report",
			"is_standard": "Yes",
			"add_total_row": 1,
			"roles": [{"role": "Stock User"}, {"role": "Stock Manager"}],
		}
	).insert(ignore_permissions=True)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 100},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 130},
		{"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": _("Qty Written Off"), "fieldname": "qty_out", "fieldtype": "Float", "width": 130},
		{"label": _("Loss Value"), "fieldname": "loss_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
		{"label": _("Responsible User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 160},
	]

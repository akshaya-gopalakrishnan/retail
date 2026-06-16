import frappe
from frappe import _
from frappe.utils import flt

from retail.retail_app.report.stock_movement_utils import get_stock_movements


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_data(filters=None):
	data = []
	amount_cache = {}

	for row in get_stock_movements(filters):
		if row.movement_type not in (_("Sale"), _("Return")):
			continue

		sales_amount = get_sales_amount(row, amount_cache)
		cost_amount = -flt(row.stock_value_difference)
		gross_profit = sales_amount - cost_amount
		margin_percent = (gross_profit / sales_amount * 100) if sales_amount else 0

		row.sales_amount = sales_amount
		row.cost_amount = cost_amount
		row.gross_profit = gross_profit
		row.margin_percent = margin_percent
		row.qty = row.qty_out or row.qty_in
		data.append(row)

	return data


def get_sales_amount(row, amount_cache):
	if row.voucher_type not in ("Sales Invoice", "POS Invoice"):
		return 0

	key = (row.voucher_type, row.voucher_detail_no)
	if key in amount_cache:
		return amount_cache[key]

	table = "Sales Invoice Item" if row.voucher_type == "Sales Invoice" else "POS Invoice Item"
	amount = frappe.db.get_value(table, row.voucher_detail_no, "base_net_amount") or 0
	amount_cache[key] = flt(amount)
	return amount_cache[key]


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Movement Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 120},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("Sales Amount"), "fieldname": "sales_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Cost Amount"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 120},
		{"label": _("Customer"), "fieldname": "party", "fieldtype": "Data", "width": 160},
		{"label": _("POS Profile"), "fieldname": "pos_profile_display", "fieldtype": "Link", "options": "POS Profile", "width": 140},
		{"label": _("Cashier / User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 160},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
	]

from collections import defaultdict

from frappe import _
from frappe.utils import flt

from retail.retail_app.report.stock_movement_utils import get_stock_movements, is_damage_movement, is_expiry_movement


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_data(filters=None):
	day_map = defaultdict(lambda: defaultdict(float))

	for row in get_stock_movements(filters):
		date_key = row.posting_date
		day = day_map[date_key]
		day["posting_date"] = date_key
		day["net_qty"] += flt(row.net_qty)
		day["net_stock_value_change"] += flt(row.stock_value_difference)

		if row.movement_type == _("Sale"):
			day["sales_qty"] += flt(row.qty_out)
			day["sales_cost"] += abs(flt(row.stock_value_difference))
		elif row.movement_type == _("Return"):
			day["return_qty"] += flt(row.qty_in)
			day["return_value"] += abs(flt(row.stock_value_difference))
		elif row.movement_type == _("Purchase"):
			day["purchase_qty"] += flt(row.qty_in)
			day["purchase_value"] += flt(row.stock_value_difference)
		elif row.movement_type == _("Purchase Return"):
			day["purchase_return_qty"] += flt(row.qty_out)
			day["purchase_return_value"] += abs(flt(row.stock_value_difference))
		elif row.voucher_type == "Stock Reconciliation":
			day["adjustment_qty"] += abs(flt(row.net_qty))
			day["adjustment_value"] += flt(row.stock_value_difference)
		elif row.voucher_type == "Stock Entry" and is_expiry_movement(row):
			day["expiry_loss_qty"] += flt(row.qty_out)
			day["expiry_loss_value"] += abs(flt(row.stock_value_difference))
		elif row.voucher_type == "Stock Entry" and is_damage_movement(row):
			day["damage_qty"] += flt(row.qty_out)
			day["damage_value"] += abs(flt(row.stock_value_difference))
		elif row.voucher_type == "Stock Entry":
			day["stock_entry_qty"] += abs(flt(row.net_qty))
			day["stock_entry_value"] += flt(row.stock_value_difference)

	return [day_map[key] for key in sorted(day_map, reverse=True)]


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Sales Qty"), "fieldname": "sales_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Sales Cost"), "fieldname": "sales_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Return Qty"), "fieldname": "return_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Purchase Qty"), "fieldname": "purchase_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Purchase Value"), "fieldname": "purchase_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Purchase Return Qty"), "fieldname": "purchase_return_qty", "fieldtype": "Float", "width": 140},
		{"label": _("Damage Qty"), "fieldname": "damage_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Damage Value"), "fieldname": "damage_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Expiry Loss Qty"), "fieldname": "expiry_loss_qty", "fieldtype": "Float", "width": 130},
		{"label": _("Expiry Loss Value"), "fieldname": "expiry_loss_value", "fieldtype": "Currency", "width": 140},
		{"label": _("Adjustment Qty"), "fieldname": "adjustment_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Net Qty"), "fieldname": "net_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Net Stock Value Change"), "fieldname": "net_stock_value_change", "fieldtype": "Currency", "width": 170},
	]

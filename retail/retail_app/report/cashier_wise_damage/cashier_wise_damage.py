from frappe import _

from retail.retail_app.report.stock_movement_utils import get_stock_movements, is_damage_movement, is_expiry_movement


def execute(filters=None):
	data = []
	for row in get_stock_movements(filters):
		if is_damage_movement(row) and not is_expiry_movement(row):
			row.damage_value = abs(row.stock_value_difference or 0)
			data.append(row)

	return get_columns(), data


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Cashier / User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 170},
		{"label": _("Damage Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 140},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": _("Qty"), "fieldname": "qty_out", "fieldtype": "Float", "width": 90},
		{"label": _("Value"), "fieldname": "damage_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
	]

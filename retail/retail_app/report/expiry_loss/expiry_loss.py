from frappe import _

from retail.retail_app.report.stock_movement_utils import get_stock_movements, is_expiry_movement


def execute(filters=None):
	data = []
	for row in get_stock_movements(filters):
		if is_expiry_movement(row) or (row.expiry_date and row.voucher_type == "Stock Entry" and row.qty_out):
			row.loss_value = abs(row.stock_value_difference or 0)
			data.append(row)

	return get_columns(), data


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Movement Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 140},
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

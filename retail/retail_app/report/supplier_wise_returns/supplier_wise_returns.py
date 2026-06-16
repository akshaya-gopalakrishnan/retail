from frappe import _

from retail.retail_app.report.stock_movement_utils import get_stock_movements


def execute(filters=None):
	data = []
	for row in get_stock_movements(filters):
		if row.movement_type == _("Purchase Return"):
			row.returned_value = abs(row.stock_value_difference or 0)
			data.append(row)

	return get_columns(), data


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Supplier"), "fieldname": "party", "fieldtype": "Link", "options": "Supplier", "width": 180},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": _("Returned Qty"), "fieldname": "qty_out", "fieldtype": "Float", "width": 110},
		{"label": _("Returned Value"), "fieldname": "returned_value", "fieldtype": "Currency", "width": 130},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
	]

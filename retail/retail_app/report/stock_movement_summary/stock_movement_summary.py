from frappe import _

from retail.retail_app.report.stock_movement_utils import get_stock_movements


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_data(filters=None):
	return get_stock_movements(filters)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Movement Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 140},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Qty In"), "fieldname": "qty_in", "fieldtype": "Float", "width": 90},
		{"label": _("Qty Out"), "fieldname": "qty_out", "fieldtype": "Float", "width": 90},
		{"label": _("Net Qty"), "fieldname": "net_qty", "fieldtype": "Float", "width": 90},
		{"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Value Change"), "fieldname": "stock_value_difference", "fieldtype": "Currency", "width": 120},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
		{"label": _("Stock Entry Type"), "fieldname": "stock_entry_type", "fieldtype": "Link", "options": "Stock Entry Type", "width": 150},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 160},
		{"label": _("Responsible User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 160},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
	]

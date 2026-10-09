from frappe import _

from retail.retail_app.report.van_sales_report_utils import get_van_stock_items, normalize_filters


def execute(filters=None):
	filters = normalize_filters(filters)
	return get_columns(), get_data(filters), None, None, None, 1


def get_data(filters):
	return [
		{
			"posting_date": row.posting_date,
			"stock_entry": row.stock_entry,
			"van_session": row.van_session,
			"van": row.van,
			"driver": row.driver,
			"driver_name": row.driver_name,
			"item_code": row.item_code,
			"item_name": row.item_name,
			"s_warehouse": row.s_warehouse,
			"t_warehouse": row.t_warehouse,
			"qty": row.transfer_qty or row.qty,
			"uom": row.stock_uom or row.uom,
			"basic_rate": row.basic_rate,
			"amount": row.basic_amount or row.amount,
		}
		for row in get_van_stock_items(filters, "Wastage")
	]


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Stock Entry"), "fieldname": "stock_entry", "fieldtype": "Link", "options": "Stock Entry", "width": 160},
		{"label": _("Van Session"), "fieldname": "van_session", "fieldtype": "Link", "options": "Van Session", "width": 160},
		{"label": _("Van"), "fieldname": "van", "fieldtype": "Link", "options": "Van Fleet", "width": 120},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 150},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 140},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Source Warehouse"), "fieldname": "s_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
		{"label": _("Target Warehouse"), "fieldname": "t_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Rate"), "fieldname": "basic_rate", "fieldtype": "Currency", "width": 110},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
	]

import frappe
from frappe import _
from retail.retail_app.report.van_sales_report_utils import normalize_filters


def execute(filters=None):
    from retail.retail_app.report.profitability import profitability_rows, report_result
    filters = normalize_filters(filters)
    return report_result(profitability_rows(filters, van=True), get_columns(), ['item_code', 'item_name', 'van', 'driver', 'driver_name'])


def get_columns():
	return [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Van"), "fieldname": "van", "fieldtype": "Link", "options": "Van Fleet", "width": 120},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 150},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 140},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 130},
		{"label": _("COGS"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 130},
		{"label": _("Gross Profit Margin %"), "fieldname": "profit_percent", "fieldtype": "Percent", "width": 100},
	]

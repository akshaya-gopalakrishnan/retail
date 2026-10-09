import frappe
from frappe import _
from retail.retail_app.report.van_sales_report_utils import normalize_filters


def execute(filters=None):
    from retail.retail_app.report.profitability import profitability_rows, report_result
    filters = normalize_filters(filters)
    return report_result(profitability_rows(filters, van=True), get_columns(), None)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Van Session"), "fieldname": "van_session", "fieldtype": "Link", "options": "Van Session", "width": 160},
		{"label": _("Van"), "fieldname": "van", "fieldtype": "Link", "options": "Van Fleet", "width": 120},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Net Rate"), "fieldname": "net_rate", "fieldtype": "Currency", "width": 110},
		{"label": _("Net Sales"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("COGS"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit Margin %"), "fieldname": "profit_percent", "fieldtype": "Percent", "width": 90},
	]

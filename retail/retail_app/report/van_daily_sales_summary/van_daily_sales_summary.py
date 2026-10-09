import frappe
from frappe import _
from retail.retail_app.report.van_sales_report_utils import normalize_filters


def execute(filters=None):
    from retail.retail_app.report.profitability import profitability_rows, report_result
    filters = normalize_filters(filters)
    return report_result(profitability_rows(filters, van=True), get_columns(), ['posting_date', 'van_session', 'van', 'driver', 'driver_name'])


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Van Session"), "fieldname": "van_session", "fieldtype": "Link", "options": "Van Session", "width": 170},
		{"label": _("Van"), "fieldname": "van", "fieldtype": "Link", "options": "Van Fleet", "width": 120},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 150},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 140},
		{"label": _("Invoices"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 90},
		{"label": _("Returns"), "fieldname": "return_count", "fieldtype": "Int", "width": 90},
		{"label": _("Sales Before Returns (excl. VAT, after discounts)"), "fieldname": "gross_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("COGS"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit Margin %"), "fieldname": "profit_percent", "fieldtype": "Percent", "width": 90},
		{"label": _("Items Sold"), "fieldname": "items_sold", "fieldtype": "Float", "width": 100},
		{"label": _("Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Average Bill"), "fieldname": "average_bill_value", "fieldtype": "Currency", "width": 120},
	]

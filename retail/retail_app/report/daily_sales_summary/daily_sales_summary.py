import frappe
from frappe import _


def execute(filters=None):
    from retail.retail_app.report.profitability import profitability_rows, report_result
    filters = frappe._dict(filters or {})
    return report_result(profitability_rows(filters, van=False), get_columns(), ['posting_date', 'counter'])


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Counter"),
			"fieldname": "counter",
			"fieldtype": "Data",
			"width": 160,
		},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Return Count"), "fieldname": "return_count", "fieldtype": "Int", "width": 110},
		{"label": _("Sales Before Returns (excl. VAT, after discounts)"), "fieldname": "gross_sales", "fieldtype": "Currency", "width": 130},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 130},
		{"label": _("COGS"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 130},
		{"label": _("Gross Profit Margin %"), "fieldname": "profit_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Items Sold"), "fieldname": "items_sold", "fieldtype": "Float", "width": 110},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 130},
		{
			"label": _("Outstanding Amount"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Average Bill Value"),
			"fieldname": "average_bill_value",
			"fieldtype": "Currency",
			"width": 150,
		},
	]

"""Daily POS sales and posted gross profit, one row per original POS bill."""
import frappe
from frappe import _
from retail.retail_app.report.pos_report_utils import get_filters


def execute(filters=None):
    from retail.module_access import require
    from retail.retail_app.report.profitability import profitability_rows, report_result
    require("POS")
    filters = get_filters(filters)
    if not filters.get("company"):
        frappe.throw(_("Please select a Company."))
    return report_result(profitability_rows(filters, "POS Invoice"), get_columns(),
        ["pos_invoice", "invoice_no", "posting_date", "customer_name", "sales_invoice", "transaction_type"])


def get_columns():
	return [
		{"label": _("POS Invoice"), "fieldname": "pos_invoice", "fieldtype": "Link", "options": "POS Invoice", "width": 150},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 85},
		{"label": _("Net Sales (excl. VAT)"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 155},
		{"label": _("COGS"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Cost Status"), "fieldname": "cost_status", "fieldtype": "Data", "width": 170},
		{"label": _("Consolidated Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 200},
	]

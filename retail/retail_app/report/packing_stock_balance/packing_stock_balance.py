import frappe

from erpnext.stock.report.stock_balance.stock_balance import execute as stock_balance_execute

from retail.retail_app.report.packing_report_utils import add_packing_columns, expand_rows_with_packings


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("valuation_field_type", "Currency")
	columns, data = stock_balance_execute(filters)
	return add_packing_columns(columns), expand_rows_with_packings(data)

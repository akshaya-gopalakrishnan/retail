import frappe

from erpnext.stock.report.stock_ledger.stock_ledger import execute as stock_ledger_execute

from retail.retail_app.report.packing_report_utils import add_packing_columns, expand_rows_with_packings


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("valuation_field_type", "Currency")
	columns, data = stock_ledger_execute(filters)
	return add_packing_columns(columns), expand_rows_with_packings(data)

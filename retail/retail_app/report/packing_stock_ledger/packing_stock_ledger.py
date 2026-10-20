import frappe

from erpnext.stock.report.stock_ledger.stock_ledger import execute as stock_ledger_execute

from retail.retail_app.report.packing_report_utils import add_packing_columns, expand_rows_with_packings


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("valuation_field_type", "Currency")
	columns, data = stock_ledger_execute(filters)
	from retail.report_transaction_identity import enrich_stock_ledger
	from retail.transaction_identity import append_columns, columns as identity_columns
	enrich_stock_ledger(data)
	return append_columns(add_packing_columns(columns), identity_columns(sold=False)), expand_rows_with_packings(data)

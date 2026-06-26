"""Daily Profit Report backed by ERPNext's standard Gross Profit calculation."""

import frappe

from erpnext.accounts.report.gross_profit.gross_profit import execute as execute_gross_profit


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("group_by", "Invoice")
	filters.setdefault("include_returned_invoices", 1)
	return execute_gross_profit(filters)

import frappe
from retail.promotions.history import columns, report_rows, execute_summary


def execute(filters=None):
    return execute_summary(filters)

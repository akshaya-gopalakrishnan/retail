"""Bound the interactive Stock Ledger without altering its stock calculations."""
import frappe
from frappe import _


def stock_ledger(filters, execute):
    filters = frappe._dict(filters or {})
    if not any(filters.get(key) for key in (
        "item_code", "item_group", "warehouse", "voucher_no", "barcode", "batch_no", "serial_no",
    )):
        from erpnext.stock.report.stock_ledger.stock_ledger import get_columns
        frappe.msgprint(_("Choose an item, item group, warehouse, voucher, barcode, batch, or serial number."))
        return get_columns(filters), []
    result = execute(filters)
    if len(result[1]) > 500:
        frappe.msgprint(_("Showing the first 500 of {0} Stock Ledger rows. Narrow the filters for the complete ledger.").format(len(result[1])))
        return (result[0], result[1][:500], *result[2:])
    return result

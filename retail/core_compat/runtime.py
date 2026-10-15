"""Site-scoped adapter for the internal ERPNext price-master writer.

v15 has no hook around insert_item_price. Install one idempotent wrapper rather
than replacing item-detail calculations or changing Stock Settings. The wrapper
always delegates for sites without Retail and for all non-invoice documents.
"""
from functools import wraps

import frappe


def install(*args, **kwargs):
    from erpnext.stock import get_item_details as core

    if getattr(core.insert_item_price, "_retail_invoice_guard", False) is True:
        return
    original = core.insert_item_price

    @wraps(original)
    def insert_item_price(args):
        if (args.get("parenttype") or args.get("doctype")) in {"Sales Invoice", "POS Invoice"}:
            if "retail" in frappe.get_installed_apps():
                return
        return original(args)

    insert_item_price._retail_invoice_guard = True
    core.insert_item_price = insert_item_price


class InvoicePriceProtection:
    def set_missing_item_details(self, *args, **kwargs):
        # Also cover direct document operations outside HTTP/worker entrypoints.
        install()
        return super().set_missing_item_details(*args, **kwargs)

"""Site-scoped adapter for the internal ERPNext price-master writer.

v15 has no hook around insert_item_price. Install one idempotent wrapper rather
than replacing item-detail calculations or changing Stock Settings. The wrapper
always delegates for sites without Retail and for all non-invoice documents.
"""
from functools import wraps

import frappe


def install(*args, **kwargs):
    from erpnext.stock import get_item_details as core

    _install_purchase_master_fallback(core)
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


def _install_purchase_master_fallback(core):
    if getattr(core.get_price_list_rate_for, "_retail_purchase_master_fallback", False) is True:
        return
    original = core.get_price_list_rate_for

    @wraps(original)
    def get_price_list_rate_for(args, item_code):
        rate = original(args, item_code)
        if (rate is not None
            or (args.get("parenttype") or args.get("doctype")) not in {"Purchase Receipt", "Purchase Invoice"}
            or args.get("price_list") != "Standard Buying"
            or "retail" not in frappe.get_installed_apps()):
            return rate
        from retail.domains.item.item_price_sync import get_purchase_master_lookup_rate
        return get_purchase_master_lookup_rate(args, item_code)

    get_price_list_rate_for._retail_purchase_master_fallback = True
    core.get_price_list_rate_for = get_price_list_rate_for


class InvoicePriceProtection:
    def set_missing_item_details(self, *args, **kwargs):
        # Also cover direct document operations outside HTTP/worker entrypoints.
        install()
        return super().set_missing_item_details(*args, **kwargs)

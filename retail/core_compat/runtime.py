"""Site-scoped adapter for the internal ERPNext price-master writer.

v15 has no hook around insert_item_price. Install one idempotent wrapper rather
than replacing item-detail calculations or changing Stock Settings. The wrapper
always delegates for sites without Retail and for all non-invoice documents.
"""
from functools import wraps

import frappe


def install(*args, **kwargs):
    _install_error_response_guard()
    _install_batch_negative_stock_setting()
    _install_sales_negative_stock_valuation()
    from erpnext.stock import get_item_details as core
    from retail.promotions.whole_bill import install as install_whole_bill

    from retail.core_compat.closing_permissions import install as install_closing_permissions

    install_closing_permissions()
    install_whole_bill()
    _install_purchase_master_fallback(core)
    _install_sales_master_fallback(core)
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


def _install_batch_negative_stock_setting():
    """Apply the existing Stock Settings switch to the batch total check too."""
    from erpnext.stock import serial_batch_bundle as core

    if getattr(core.throw_negative_batch_validation, "_retail_stock_setting", False) is True:
        return
    original = core.throw_negative_batch_validation

    @wraps(original)
    def throw_negative_batch_validation(batch_no, qty):
        if frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"):
            return
        return original(batch_no, qty)

    throw_negative_batch_validation._retail_stock_setting = True
    core.throw_negative_batch_validation = throw_negative_batch_validation


def _install_sales_negative_stock_valuation():
    """Permit a missing-cost sales fallback under the negative-stock setting."""
    from erpnext.stock import stock_ledger as core

    if getattr(core.get_valuation_rate, "_retail_sales_negative_stock", False) is True:
        return
    original = core.get_valuation_rate

    @wraps(original)
    def get_valuation_rate(item_code, warehouse, voucher_type, voucher_no,
                           allow_zero_rate=False, *args, **kwargs):
        enabled = voucher_type == "Sales Invoice" and frappe.db.get_single_value(
            "Stock Settings", "allow_negative_stock"
        )
        rate = original(item_code, warehouse, voucher_type, voucher_no,
                        allow_zero_rate or bool(enabled), *args, **kwargs)
        return 0.0 if enabled and rate is None else rate

    get_valuation_rate._retail_sales_negative_stock = True
    core.get_valuation_rate = get_valuation_rate


def _install_error_response_guard():
    """Keep validation responses intact when a development console disconnects."""
    if getattr(frappe.errprint, "_retail_broken_pipe_guard", False) is True:
        return
    original = frappe.errprint

    @wraps(original)
    def errprint(msg):
        try:
            return original(msg)
        except BrokenPipeError:
            # Core prints before adding the traceback to the request-local
            # response. A closed stdout pipe must not replace the real error.
            frappe.error_log.append({"exc": frappe.as_unicode(msg)})

    errprint._retail_broken_pipe_guard = True
    frappe.errprint = errprint


def _install_purchase_master_fallback(core):
    if getattr(core.get_price_list_rate_for, "_retail_purchase_master_fallback", False) is True:
        return
    original = core.get_price_list_rate_for

    @wraps(original)
    def get_price_list_rate_for(args, item_code):
        rate = original(args, item_code)
        if (rate is not None
            or (args.get("parenttype") or args.get("doctype")) not in core.purchase_doctypes
            or args.get("price_list") != "Standard Buying"
            or "retail" not in frappe.get_installed_apps()):
            return rate
        from retail.domains.item.item_price_sync import get_purchase_master_lookup_rate
        return get_purchase_master_lookup_rate(args, item_code)

    get_price_list_rate_for._retail_purchase_master_fallback = True
    core.get_price_list_rate_for = get_price_list_rate_for


def _install_sales_master_fallback(core):
    if getattr(core.get_price_list_rate_for, "_retail_sales_master_fallback", False) is True:
        return
    original = core.get_price_list_rate_for

    @wraps(original)
    def get_price_list_rate_for(args, item_code):
        rate = original(args, item_code)
        from retail.domains.transactions.trading_vat import lookup_rate
        if rate is not None and "retail" in frappe.get_installed_apps():
            return lookup_rate(args, item_code, rate)
        if (rate is not None
            or (args.get("parenttype") or args.get("doctype")) not in {"Quotation", "Sales Order", "Delivery Note", "Sales Invoice"}
            or args.get("price_list") != "Standard Selling"
            or "retail" not in frappe.get_installed_apps()):
            return rate
        from retail.domains.item.item_price_sync import get_sales_master_lookup_rate
        return lookup_rate(args, item_code, get_sales_master_lookup_rate(args, item_code))

    get_price_list_rate_for._retail_sales_master_fallback = True
    core.get_price_list_rate_for = get_price_list_rate_for


class InvoicePriceProtection:
    def set_missing_item_details(self, *args, **kwargs):
        # Also cover direct document operations outside HTTP/worker entrypoints.
        install()
        return super().set_missing_item_details(*args, **kwargs)

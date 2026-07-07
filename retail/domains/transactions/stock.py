"""Stock safeguards for standalone retail invoices."""

import frappe


def set_update_stock_for_standalone_invoice(doc, method=None):
	"""Update stock on standalone stock-item invoices.

	ERPNext Gross Profit reads stock valuation. A standalone invoice that does not
	update stock has no Stock Ledger Entry, so the report falls back to the last
	available stock valuation instead of the invoice's current item cost.
	"""
	if doc.doctype not in {"Purchase Invoice", "Sales Invoice"}:
		return
	if not doc.meta.has_field("update_stock"):
		return
	if doc.get("update_stock"):
		return

	stock_items = [item for item in doc.get("items", []) if _is_stock_item(item.get("item_code"))]
	if not stock_items:
		return

	if doc.doctype == "Purchase Invoice" and all(not item.get("purchase_receipt") for item in stock_items):
		doc.update_stock = 1
	elif doc.doctype == "Sales Invoice" and all(not item.get("delivery_note") for item in stock_items):
		doc.update_stock = 1


def _is_stock_item(item_code):
	if not item_code:
		return False
	return bool(frappe.get_cached_value("Item", item_code, "is_stock_item"))

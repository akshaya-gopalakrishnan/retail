"""Explicit, audited PR/PI updates of maintained Item Master rates.

Master rates use company currency and stock UOM. VAT is recalculated from the
Item's respective tax template, so subsequent Item saves preserve the values.
Cancellation does not reverse maintained defaults; use Retail Item Rate Audit.
"""

import frappe
from frappe.utils import flt

from retail.domains.item import rate_audit


def update_purchase_master_rates(doc):
	if not flt(doc.get("custom_update_item_master_rates")) or doc.get("is_return"):
		return
	rate_audit._require_price_manager()
	for row in doc.get("items") or []:
		if not row.get("item_code") or flt(row.get("qty")) <= 0:
			continue
		item = frappe.get_doc("Item", row.item_code)
		factor = _factor(item, row.get("uom"), row.get("conversion_factor"))
		# Zero is meaningful (free goods); never fall back to the undiscounted rate.
		rate = row.get("base_net_rate")
		if rate is None:
			rate = flt(row.get("net_rate")) * _currency_factor(doc, doc.get("currency"))
		_apply(doc, row, item, "Purchase", flt(rate) / factor, row.get("uom"), factor)


def update_selling_master_rate(doc, row, item, requests):
	if not flt(doc.get("custom_update_item_master_rates")) or doc.get("is_return"):
		return
	rate_audit._require_price_manager()
	# An explicit stock-UOM price takes precedence over independent packing prices.
	uom = item.stock_uom if flt(requests.get(item.stock_uom)) > 0 else row.get("uom")
	rate = flt(requests.get(uom))
	if rate <= 0:
		return
	factor = _factor(item, uom, row.get("conversion_factor") if uom == row.get("uom") else 1)
	currency = frappe.db.get_value("Price List", "Standard Selling", "currency")
	rate = rate * _currency_factor(doc, currency) / factor
	_apply(doc, row, item, "Selling", rate, uom, factor)


def _factor(item, uom, factor):
	if not uom or uom == item.stock_uom:
		return 1
	factor = flt(factor)
	if factor <= 0:
		frappe.throw(f"Missing positive conversion factor for {item.name} / {uom}.")
	return factor


def _currency_factor(doc, currency):
	base_currency = frappe.db.get_value("Company", doc.company, "default_currency")
	if currency == base_currency:
		return 1
	if currency == doc.get("currency") and flt(doc.get("conversion_rate")) > 0:
		return flt(doc.conversion_rate)
	frappe.throw("Cannot convert the rate currency to the company's currency for Item Master.")


def _apply(doc, row, item, direction, net_rate, uom, factor):
	if net_rate <= 0:
		return
	rate_audit._apply_item_rate_update(
		item_code=item.name, direction=direction, new_net_rate=net_rate,
		source_doctype=doc.doctype, source_name=doc.name, source_row=row.name,
		supplier=doc.get("supplier"), uom=uom or item.stock_uom,
		conversion_factor=factor, vat_basis="Excluding VAT",
		remarks="PR/PI Item Master checkbox: company currency, stock UOM; VAT from Item tax template.",
	)
	frappe.clear_document_cache("Item", item.name)

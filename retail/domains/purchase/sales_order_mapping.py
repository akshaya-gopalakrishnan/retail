"""Recalculate purchase VAT helpers after native Sales Order mapping."""

import frappe

from erpnext.selling.doctype.sales_order.sales_order import make_purchase_order as native_make_purchase_order

from retail.domains.transactions.vat import set_vat_rates


@frappe.whitelist()
def make_purchase_order(source_name, selected_items=None, target_doc=None):
	doc = native_make_purchase_order(source_name, selected_items, target_doc)
	if doc is None:
		return
	# Native mapping excludes selling rates, but same-named custom helpers are
	# copied. Clear those inputs so a zero buying rate cannot revive a sale price.
	for row in doc.items:
		row.custom_rate_including_vat = 0
		row.custom_amount_including_vat = 0
		row.custom_vat_amount = 0
	set_vat_rates(doc)
	return doc

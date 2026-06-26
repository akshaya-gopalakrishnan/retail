"""Keep transaction tax-template selectors out of the day-to-day Retail UI."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


TAX_TEMPLATE_DOCTYPES = (
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
)

# These fields make up the transaction-level Taxes and Charges block.  Item
# tax templates and the tax engine are deliberately not included.
TAX_UI_FIELDS = (
	"taxes_section",
	"tax_category",
	"taxes_and_charges",
	"shipping_rule",
	"incoterm",
	"named_place",
	"taxes",
	"totals",
	"base_taxes_and_charges_added",
	"base_taxes_and_charges_deducted",
	"base_total_taxes_and_charges",
	"taxes_and_charges_added",
	"taxes_and_charges_deducted",
	"total_taxes_and_charges",
)


def hide_transaction_tax_templates():
	"""Hide only the template selector; tax calculations remain enabled."""
	set_transaction_tax_template_visibility(hidden=True)


def set_transaction_tax_template_visibility(*, hidden: bool):
	"""Set visibility centrally; use ``hidden=False`` to restore the UI."""
	value = "1" if hidden else "0"
	for doctype in TAX_TEMPLATE_DOCTYPES:
		meta = frappe.get_meta(doctype)
		for fieldname in TAX_UI_FIELDS:
			if meta.has_field(fieldname):
				_set_hidden_property(doctype, fieldname, value)

	frappe.clear_cache()


def _set_hidden_property(doctype, fieldname, value):
	property_setter_name = f"{doctype}-{fieldname}-hidden"
	if frappe.db.exists("Property Setter", property_setter_name):
		frappe.db.set_value("Property Setter", property_setter_name, "value", value, update_modified=False)
		return

	make_property_setter(
		doctype,
		fieldname,
		"hidden",
		value,
		"Check",
		validate_fields_for_doctype=False,
	)

"""Retail transaction naming-series defaults.

The series are intentionally generic (``RTL``) so the Retail app can be
installed for any company or site.  Existing documents are never renamed.
"""

from __future__ import annotations

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


NAMING_SERIES_OPTIONS = {
	"Journal Entry": ("RTL-JV-.YYYY.-", "RTL-OPEN-JV-.YYYY.-"),
	"Payment Entry": ("RTL-PAY-.YYYY.-", "RTL-RCV-.YYYY.-", "RTL-CON-.YYYY.-"),
	"Sales Invoice": ("RTL-SINV-.YYYY.-", "RTL-SINV-RET-.YYYY.-"),
	"Purchase Invoice": ("RTL-PINV-.YYYY.-", "RTL-PINV-RET-.YYYY.-"),
	"Sales Order": ("RTL-SO-.YYYY.-",),
	"Purchase Order": ("RTL-PO-.YYYY.-",),
	"Delivery Note": ("RTL-DN-.YYYY.-", "RTL-DN-RET-.YYYY.-"),
	"Purchase Receipt": ("RTL-PR-.YYYY.-", "RTL-PR-RET-.YYYY.-"),
	"Stock Entry": ("RTL-SE-.YYYY.-",),
	"Material Request": ("RTL-MR-.YYYY.-",),
}

RETURN_SERIES = {
	"Sales Invoice": "RTL-SINV-RET-.YYYY.-",
	"Purchase Invoice": "RTL-PINV-RET-.YYYY.-",
	"Delivery Note": "RTL-DN-RET-.YYYY.-",
	"Purchase Receipt": "RTL-PR-RET-.YYYY.-",
}

PAYMENT_SERIES = {
	"Pay": "RTL-PAY-.YYYY.-",
	"Receive": "RTL-RCV-.YYYY.-",
	"Internal Transfer": "RTL-CON-.YYYY.-",
}

LIST_TITLE_FIELDS = {
	"Bin": "item_code",
	"Counter": "counter_name",
}


def install_naming_series():
	"""Add Retail's editable naming-series choices to a site.

	This is idempotent and is called on new installations and by a versioned
	patch for existing installations.
	"""
	for doctype, series in NAMING_SERIES_OPTIONS.items():
		property_setter_name = f"{doctype}-naming_series-options"
		value = "\n".join(series)

		if frappe.db.exists("Property Setter", property_setter_name):
			frappe.db.set_value("Property Setter", property_setter_name, "value", value, update_modified=False)
		else:
			make_property_setter(
				doctype,
				"naming_series",
				"options",
				value,
				"Text",
				validate_fields_for_doctype=False,
			)

	frappe.clear_cache()


def install_list_titles():
	"""Use business fields, rather than opaque database names, as list titles."""
	for doctype, title_field in LIST_TITLE_FIELDS.items():
		property_setter_name = f"{doctype}-main-title_field"
		if frappe.db.exists("Property Setter", property_setter_name):
			frappe.db.set_value(
				"Property Setter", property_setter_name, "value", title_field, update_modified=False
			)
		else:
			make_property_setter(
				doctype,
				None,
				"title_field",
				title_field,
				"Data",
				for_doctype=True,
				validate_fields_for_doctype=False,
			)

		if doctype == "Counter":
			_set_doctype_property(doctype, "show_title_field_in_link", "1", "Check")
			_set_doctype_property(doctype, "search_fields", "counter_name", "Data")
			_set_doctype_property(doctype, "autoname", "field:counter_name", "Data")

	frappe.clear_cache()


def _set_doctype_property(doctype, property_name, value, property_type):
	property_setter_name = f"{doctype}-main-{property_name}"
	if frappe.db.exists("Property Setter", property_setter_name):
		frappe.db.set_value(
			"Property Setter", property_setter_name, "value", value, update_modified=False
		)
		return

	make_property_setter(
		doctype,
		None,
		property_name,
		value,
		property_type,
		for_doctype=True,
		validate_fields_for_doctype=False,
	)


def install_retail_defaults():
	from retail.domains.sales.counter import ensure_counter_display_field
	from retail.domains.item.naming import install_item_code_defaults
	from retail.domains.item.item_price_sync import (
		disable_legacy_item_price_scripts,
		ensure_standard_purchase_rate_field,
	)
	from retail.domains.item.packing_rate import ensure_packing_purchase_rate_script
	from retail.tax_visibility import hide_transaction_tax_templates
	from retail.domains.item.vat_pricing import ensure_item_vat_pricing_fields

	install_naming_series()
	install_list_titles()
	ensure_counter_display_field()
	install_item_code_defaults()
	disable_legacy_item_price_scripts()
	ensure_standard_purchase_rate_field()
	hide_transaction_tax_templates()
	ensure_packing_purchase_rate_script()
	ensure_item_vat_pricing_fields()


def set_transaction_naming_series(doc, method=None):
	"""Choose the correct series for transaction types that have variants."""
	if doc.doctype == "Payment Entry":
		_set_if_retail_default(doc, PAYMENT_SERIES.get(doc.payment_type))
		return

	if doc.doctype == "Journal Entry":
		series = "RTL-OPEN-JV-.YYYY.-" if doc.voucher_type == "Opening Entry" else "RTL-JV-.YYYY.-"
		_set_if_retail_default(doc, series)
		return

	if doc.doctype in RETURN_SERIES and doc.is_return:
		if _is_copied_source_series_or_retail_default(doc):
			doc.naming_series = RETURN_SERIES[doc.doctype]


def _set_if_retail_default(doc, series):
	if not series:
		return

	if not doc.naming_series or doc.naming_series in NAMING_SERIES_OPTIONS[doc.doctype]:
		doc.naming_series = series


def _is_copied_source_series_or_retail_default(doc):
	if not doc.naming_series or doc.naming_series in NAMING_SERIES_OPTIONS[doc.doctype]:
		return True

	if not doc.return_against:
		return False

	return doc.naming_series == frappe.db.get_value(doc.doctype, doc.return_against, "naming_series")

"""Automatic, human-readable Item Code generation for Retail."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.naming import make_autoname


ITEM_NAMING_SERIES = "RTL-ITEM-.YYYY.-"


def install_item_code_defaults():
	"""Configure Item forms so users enter a name, not a technical code."""
	frappe.db.set_single_value("Stock Settings", "item_naming_by", "Naming Series")
	_set_field_property("naming_series", "options", ITEM_NAMING_SERIES, "Text")
	_set_field_property("naming_series", "hidden", "1", "Check")
	_set_field_property("item_code", "reqd", "0", "Check")
	_set_field_property("item_code", "read_only", "1", "Check")
	_set_field_property("item_name", "reqd", "1", "Check")
	frappe.clear_cache(doctype="Item")


def set_automatic_item_code(doc, method=None):
	"""Generate an Item Code when one was not supplied by an integration."""
	if doc.item_code:
		return

	doc.naming_series = ITEM_NAMING_SERIES
	doc.item_code = make_autoname(f"{ITEM_NAMING_SERIES}.#####", doc=doc)


def _set_field_property(fieldname, property_name, value, property_type):
	property_setter_name = f"Item-{fieldname}-{property_name}"
	if frappe.db.exists("Property Setter", property_setter_name):
		frappe.db.set_value("Property Setter", property_setter_name, "value", value, update_modified=False)
		return

	make_property_setter(
		"Item",
		fieldname,
		property_name,
		value,
		property_type,
		validate_fields_for_doctype=False,
	)

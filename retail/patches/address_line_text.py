"""Allow long address lines while preserving the native Address field."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	make_property_setter("Address", "address_line1", "fieldtype", "Small Text", "Select")
	make_property_setter("Address", "address_line1", "length", 0, "Int")
	frappe.db.updatedb("Address")

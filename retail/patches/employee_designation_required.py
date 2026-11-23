"""Require designation using native Employee form and save validation."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def install():
	if not frappe.db.exists("DocType", "Employee"):
		return
	field = frappe.get_meta("Employee").get_field("designation")
	if field and not field.reqd:
		make_property_setter("Employee", "designation", "reqd", "1", "Check")
	frappe.clear_cache(doctype="Employee")

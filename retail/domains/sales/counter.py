"""Counter display helpers that preserve existing document links."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_counter_display_field():
	"""Add a stored display name for Sales Invoice counter links."""
	create_custom_fields(
		{
			"Sales Invoice": [
				{
					"fieldname": "custom_counter_name",
					"label": "Counter Name",
					"fieldtype": "Data",
					"read_only": 1,
					"allow_on_submit": 1,
					"hidden": 1,
					"no_copy": 1,
				}
			]
		},
		ignore_validate=True,
	)
	backfill_sales_invoice_counter_names()
	frappe.clear_cache(doctype="Sales Invoice")


def set_sales_invoice_counter_name(doc, method=None):
	if not doc.meta.has_field("custom_counter_name"):
		return

	doc.custom_counter_name = get_counter_display_name(doc.get("custom_counter"))


def backfill_sales_invoice_counter_names():
	if not frappe.db.has_column("Sales Invoice", "custom_counter_name"):
		return

	for invoice in frappe.get_all(
		"Sales Invoice", fields=["name", "custom_counter"], filters={"custom_counter": ["!=", ""]}
	):
		frappe.db.set_value(
			"Sales Invoice",
			invoice.name,
			"custom_counter_name",
			get_counter_display_name(invoice.custom_counter),
			update_modified=False,
		)


def get_counter_display_name(counter):
	if not counter:
		return ""

	if not frappe.db.exists("DocType", "Counter"):
		return counter

	return (
		frappe.db.get_value("Counter", counter, "counter_name")
		or frappe.db.get_value("Counter", {"counter_name": counter}, "counter_name")
		or counter
	)

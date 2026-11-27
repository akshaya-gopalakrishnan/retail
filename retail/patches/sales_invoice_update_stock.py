"""Keep mapped invoices on the native default; Desk defaults only blank invoices."""

from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	make_property_setter(
		"Sales Invoice", "update_stock", "default", "0", "Text",
		validate_fields_for_doctype=False,
	)

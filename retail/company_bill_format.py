"""Compact, company-specific bill header and footer settings."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_company_bill_format_fields():
	"""Keep Bill Format directly after Details, with three native form columns."""
	fields = []
	previous = "old_parent"

	def add(name, label, fieldtype="Data", **options):
		nonlocal previous
		fieldname = f"custom_bill_{name}"
		fields.append({
			"fieldname": fieldname,
			"label": label,
			"fieldtype": fieldtype,
			"insert_after": previous,
			**options,
		})
		previous = fieldname

	add("format_tab", "Bill Format", "Tab Break")
	add("format_section", "", "Section Break")
	add("address", "Address", "Small Text")
	add("phone", "Phone Number")
	add("email", "Email ID", options="Email")
	add("tax_id", "Tax ID")
	add("header_column", "", "Column Break")
	for index in range(1, 6):
		add(f"h{index}", f"H{index}")
	add("footer_column", "", "Column Break")
	for index in range(1, 6):
		add(f"f{index}", f"F{index}")

	create_custom_fields({"Company": fields}, update=True)

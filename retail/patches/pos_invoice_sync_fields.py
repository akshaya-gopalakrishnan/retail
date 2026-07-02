import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from retail.patches.v1_1.setup_offline_pos_sync import ensure_role, get_custom_fields


def execute():
	ensure_role()
	pos_invoice_fields = get_custom_fields()["POS Invoice"]
	# Existing fields created before the section placement was corrected need a
	# one-time rebuild; otherwise Frappe retains their old rendered positions.
	for field in pos_invoice_fields:
		name = f"POS Invoice-{field['fieldname']}"
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, force=True)
	create_custom_fields({"POS Invoice": pos_invoice_fields}, ignore_validate=True, update=True)
	for field in pos_invoice_fields:
		name = f"POS Invoice-{field['fieldname']}"
		frappe.db.set_value(
			"Custom Field",
			name,
			{"hidden": 0, "depends_on": "eval:doc.external_pos_reference"},
			update_modified=False,
		)
	frappe.clear_cache(doctype="POS Invoice")

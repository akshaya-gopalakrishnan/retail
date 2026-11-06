"""Keep ERPNext's unique name while allowing repeated human display names."""

import frappe

from retail.document_codes import FIELD, assign


def before_naming(doc, method=None):
	if not doc.get(FIELD):
		assign(doc)
	display_name = (doc.get("custom_display_name") or doc.get("sales_person_name") or "").strip()
	if not display_name:
		frappe.throw(frappe._("Sales Person Display Name is required."))
	combined = f"{doc.get(FIELD)} - {display_name}"
	if len(combined) > 140:
		frappe.throw(frappe._("Sales Person Display Name is too long for the generated ERP name."))
	doc.custom_display_name = display_name
	doc.sales_person_name = combined

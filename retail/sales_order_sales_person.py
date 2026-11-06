"""Capture the order creator's Sales Person without changing document permissions."""

import frappe

from retail.login_sales_person import get_sales_person_identity


@frappe.whitelist()
def search_sales_people(txt=""):
	people = frappe.get_list(
		"Sales Person",
		filters={"enabled": 1, "is_group": 0},
		or_filters={field: ["like", f"%{txt}%"] for field in (
			"custom_document_code", "custom_display_name", "sales_person_name"
		)},
		fields=["custom_document_code", "custom_display_name", "sales_person_name"],
		order_by="custom_document_code asc", limit_page_length=30,
	)
	return [
		{"value": person.custom_document_code,
		 "label": frappe.utils.escape_html(person.custom_document_code),
		 "description": frappe.utils.escape_html(person.custom_display_name or person.sales_person_name)}
		for person in people if person.custom_document_code
	]


def assign_creator(doc, method=None):
	identity = get_sales_person_identity(frappe.session.user)
	doc.sales_person_id = identity["sales_person_id"]
	doc.sales_person_name = identity["sales_person_name"]


def validate(doc, method=None):
	if doc.docstatus == 0 or doc.get("_action") == "submit":
		if not doc.sales_person_id:
			doc.sales_person_name = None
			return
		person = frappe.db.get_value(
			"Sales Person", {"custom_document_code": doc.sales_person_id},
			["custom_display_name", "sales_person_name"], as_dict=True,
		)
		if not person:
			frappe.throw(frappe._("Sales Person Code {0} does not exist.").format(doc.sales_person_id))
		doc.sales_person_name = person.get("custom_display_name") or person.sales_person_name

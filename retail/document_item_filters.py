"""Document-list item identity filters, using the native permission-aware query."""

from contextlib import contextmanager

import frappe
from frappe.desk import reportview
from frappe.model import get_permitted_fields


DOCTYPES = {
	"POS Invoice": "POS Invoice Item",
	"Sales Invoice": "Sales Invoice Item",
	"Purchase Order": "Purchase Order Item",
	"Purchase Invoice": "Purchase Invoice Item",
	"Purchase Receipt": "Purchase Receipt Item",
}
FLAG = "retail_document_item_filter"


def normalize(doctype, value):
	if doctype not in DOCTYPES:
		frappe.throw("Unsupported document list", frappe.ValidationError)
	frappe.has_permission(doctype, "read", throw=True)
	value = frappe.parse_json(value) if isinstance(value, str) else value
	if not isinstance(value, dict) or set(value) - {"item_code", "serial_no", "batch_no"}:
		frappe.throw("Invalid item filters", frappe.ValidationError)
	fields = get_permitted_fields(DOCTYPES[doctype], parenttype=doctype)
	result = {}
	for key, text in value.items():
		if not isinstance(text, str) or len(text) > 140 or "\n" in text or "\r" in text:
			frappe.throw("Invalid item filter value", frappe.ValidationError)
		text = text.strip()
		if not text:
			continue
		if key not in fields:
			frappe.throw("Item filter is not available for this document", frappe.PermissionError)
		result[key] = text
	return result


@contextmanager
def filtered_request():
	"""Remove our extra argument before calling native reportview validation."""
	form = frappe.local.form_dict
	value = form.pop("retail_item_filters", "{}")
	previous = frappe.flags.get(FLAG)
	try:
		criteria = normalize(form.get("doctype"), value)
		frappe.flags[FLAG] = (form.doctype, criteria)
		yield
	finally:
		frappe.flags[FLAG] = previous
		form["retail_item_filters"] = value


@frappe.whitelist()
@frappe.read_only()
def get():
	with filtered_request():
		return reportview.get()


@frappe.whitelist()
@frappe.read_only()
def get_count():
	with filtered_request():
		return reportview.get_count()


def query_conditions(user=None, doctype=None):
	active = frappe.flags.get(FLAG)
	if not active or active[0] != doctype or not active[1]:
		return ""
	criteria = active[1]
	child = DOCTYPES[doctype]
	escape = frappe.db.escape
	conditions = [
		f"ri.parent = `tab{doctype}`.name",
		f"ri.parenttype = {escape(doctype)}",
		"ri.parentfield = 'items'",
	]
	if criteria.get("item_code"):
		conditions.append(f"ri.item_code = {escape(criteria['item_code'])}")
	for field in ("serial_no", "batch_no"):
		if not criteria.get(field):
			continue
		value = escape(criteria[field])
		if field == "serial_no":
			# Serial fields contain one serial per line; avoid substring matches.
			legacy = (
				f"LOCATE(CONCAT(CHAR(10), {value}, CHAR(10)), "
				"CONCAT(CHAR(10), REPLACE(COALESCE(ri.serial_no, ''), CHAR(13), ''), CHAR(10))) > 0"
			)
		else:
			legacy = f"ri.batch_no = {value}"
		bundle = (
			"EXISTS (SELECT 1 FROM `tabSerial and Batch Entry` rbe "
			"WHERE rbe.parent = ri.serial_and_batch_bundle "
			"AND rbe.parenttype = 'Serial and Batch Bundle' "
			f"AND rbe.{field} = {value})"
		)
		conditions.append(f"({legacy} OR {bundle})")
	return f"EXISTS (SELECT 1 FROM `tab{child}` ri WHERE {' AND '.join(conditions)})"

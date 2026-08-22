import frappe
from frappe import _
from frappe.utils import flt, getdate


def validate_active_dates(doc):
	if doc.active_from and doc.active_to and getdate(doc.active_from) > getdate(doc.active_to):
		frappe.throw(_("Active From cannot be after Active To."))


def ensure_products(rows):
	if not rows:
		frappe.throw(_("Add at least one product."))


def validate_product_row(row):
	if row.item and row.item_group:
		frappe.throw(_("Row #{0}: Select either Item or Item Group, not both.").format(row.idx))

	if not row.item and not row.item_group:
		frappe.throw(_("Row #{0}: Select Item or Item Group.").format(row.idx))


def retire_scheme(scheme_name):
	if not scheme_name or not frappe.db.exists("Promotional Scheme", scheme_name):
		return

	scheme = frappe.get_doc("Promotional Scheme", scheme_name)
	scheme.disable = 1
	scheme.save(ignore_permissions=True)


def retire_linked_schemes(doc):
	for row in doc.get("linked_schemes") or []:
		retire_scheme(row.promotional_scheme)
	doc.set("linked_schemes", [])


def build_base_scheme(doc, apply_on):
	scheme_name = doc.get("promotional_scheme")
	scheme = frappe.get_doc("Promotional Scheme", scheme_name) if scheme_name and frappe.db.exists("Promotional Scheme", scheme_name) else frappe.new_doc("Promotional Scheme")

	scheme.apply_on = apply_on
	scheme.disable = doc.disabled
	scheme.selling = 1
	scheme.buying = 0
	scheme.valid_from = doc.active_from
	scheme.valid_upto = doc.active_to
	scheme.company = doc.company
	scheme.currency = doc.get("currency")
	scheme.mixed_conditions = 0
	scheme.is_cumulative = 0
	scheme.set("items", [])
	scheme.set("item_groups", [])
	scheme.set("brands", [])
	scheme.set("price_discount_slabs", [])
	scheme.set("product_discount_slabs", [])
	return scheme


def build_new_scheme(doc, apply_on):
	scheme = frappe.new_doc("Promotional Scheme")
	scheme.apply_on = apply_on
	scheme.disable = doc.disabled
	scheme.selling = 1
	scheme.buying = 0
	scheme.valid_from = doc.active_from
	scheme.valid_upto = doc.active_to
	scheme.company = doc.company
	scheme.currency = doc.get("currency")
	scheme.mixed_conditions = 0
	scheme.is_cumulative = 0
	return scheme


def add_product_to_scheme(scheme, row):
	if row.item:
		scheme.append("items", {"item_code": row.item, "uom": row.uom})
	elif row.item_group:
		scheme.append("item_groups", {"item_group": row.item_group, "uom": row.uom})


def set_scheme_link(doc, scheme):
	doc.db_set("promotional_scheme", scheme.name, update_modified=False)


def update_linked_schemes(doc):
	doc.update_child_table("linked_schemes")

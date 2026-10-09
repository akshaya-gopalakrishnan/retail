import frappe
from frappe import _
from frappe.utils import cint, flt

from retail.van_permissions import validate_van_document_access


def apply_van_sales_invoice_rules(doc, method=None):
	if not cint(doc.get("custom_is_van_sale")):
		return

	validate_van_document_access(
		doc,
		"Sales Invoice",
		_("You are not allowed to create or update Van Sales Invoices."),
	)
	session = apply_van_session_details(doc)
	validate_van_sales_invoice(doc, session)
	apply_van_warehouse_to_items(doc, session)
	validate_van_sales_invoice_items(doc, session)


def apply_van_session_details(doc):
	if not doc.get("custom_van_session"):
		return None

	session = frappe.db.get_value(
		"Van Session",
		doc.custom_van_session,
		["van", "van_warehouse", "driver", "driver_name", "status"],
		as_dict=True,
	)
	if not session:
		frappe.throw(_("Van Session {0} was not found.").format(frappe.bold(doc.custom_van_session)))

	doc.custom_van = session.van
	doc.custom_van_warehouse = session.van_warehouse
	doc.custom_driver = session.driver
	doc.custom_driver_name = session.driver_name

	if session.status != "Open":
		frappe.throw(
			_("Van Session {0} is {1}. Please select an Open session.")
			.format(frappe.bold(doc.custom_van_session), frappe.bold(session.status))
		)

	return session


def validate_van_sales_invoice(doc, session=None):
	for fieldname, label in (
		("customer", _("Customer")),
		("custom_van_session", _("Van Session")),
		("custom_van", _("Van")),
		("custom_van_warehouse", _("Van Warehouse")),
		("custom_driver", _("Driver")),
	):
		if not doc.get(fieldname):
			frappe.throw(_("{0} is required for Van Sales Invoice.").format(label))

	if session:
		expected_values = {
			"custom_van": session.van,
			"custom_van_warehouse": session.van_warehouse,
			"custom_driver": session.driver,
		}
		for fieldname, expected_value in expected_values.items():
			if doc.get(fieldname) != expected_value:
				frappe.throw(
					_("{0} does not match the selected Van Session.")
					.format(frappe.bold(doc.meta.get_label(fieldname)))
				)

	doc.update_stock = 1
	if doc.meta.has_field("set_warehouse"):
		doc.set_warehouse = doc.custom_van_warehouse


def apply_van_warehouse_to_items(doc, session=None):
	van_warehouse = session.van_warehouse if session else doc.custom_van_warehouse
	for row in doc.get("items", []):
		if row.get("item_code"):
			row.warehouse = van_warehouse


def validate_van_sales_invoice_items(doc, session=None):
	van_warehouse = session.van_warehouse if session else doc.custom_van_warehouse
	item_rows = [row for row in doc.get("items", []) if row.get("item_code")]

	if not item_rows:
		frappe.throw(_("At least one item is required for Van Sales Invoice."))

	for row in item_rows:
		qty = flt(row.get("qty"))
		if doc.get("is_return"):
			if qty >= 0:
				frappe.throw(
					_("Row #{0}: Qty must be less than zero for Van Sales Invoice Return.")
					.format(row.idx)
				)
		elif qty <= 0:
			frappe.throw(
				_("Row #{0}: Qty must be greater than zero for Van Sales Invoice.")
				.format(row.idx)
			)

		if row.get("warehouse") != van_warehouse:
			frappe.throw(
				_("Row #{0}: Warehouse must be the selected Van Warehouse {1}.")
				.format(row.idx, frappe.bold(van_warehouse))
			)

import frappe
from frappe import _
from frappe.utils import cint, flt

from retail.van_permissions import has_van_partition_permission

VAN_SALES_ROLES = {"Van Sales User", "Van Sales Manager"}
ACCOUNTING_ROLES = {"Accounts User", "Accounts Manager", "System Manager"}


def apply_van_payment_rules(doc, method=None):
	infer_van_payment_from_references(doc)

	is_van_payment = cint(doc.get("custom_is_van_payment"))
	if not is_van_payment:
		validate_non_van_payment_access(doc)
		return

	validate_van_payment_access()
	apply_van_session_details(doc)
	validate_van_payment(doc)
	validate_van_payment_references(doc)


def infer_van_payment_from_references(doc):
	if cint(doc.get("custom_is_van_payment")):
		return

	for row in doc.get("references") or []:
		if row.reference_doctype != "Sales Invoice" or not row.reference_name:
			continue

		invoice = frappe.db.get_value(
			"Sales Invoice",
			row.reference_name,
			["custom_is_van_sale", "custom_van_session"],
			as_dict=True,
		)
		if invoice and cint(invoice.custom_is_van_sale):
			doc.custom_is_van_payment = 1
			if invoice.custom_van_session and not doc.get("custom_van_session"):
				doc.custom_van_session = invoice.custom_van_session
			break


def validate_non_van_payment_access(doc):
	if _is_system_user():
		return

	roles = set(frappe.get_roles())
	if roles.intersection(VAN_SALES_ROLES) and not roles.intersection(ACCOUNTING_ROLES):
		frappe.throw(_("Please use Van Payments for Van Sales collections."))


def validate_van_payment_access():
	if _is_system_user():
		return

	if not set(frappe.get_roles()).intersection(VAN_SALES_ROLES):
		frappe.throw(_("You are not allowed to create or update Van Payments."))


def apply_van_session_details(doc):
	if not doc.get("custom_van_session"):
		return

	session = frappe.db.get_value(
		"Van Session",
		doc.custom_van_session,
		["van", "driver", "driver_name", "status"],
		as_dict=True,
	)
	if not session:
		frappe.throw(_("Van Session {0} was not found.").format(frappe.bold(doc.custom_van_session)))

	doc.custom_van = session.van
	doc.custom_driver = session.driver
	doc.custom_driver_name = session.driver_name

	if session.status != "Open":
		frappe.throw(
			_("Van Session {0} is {1}. Please select an open session.")
			.format(frappe.bold(doc.custom_van_session), frappe.bold(session.status))
		)


def validate_van_payment(doc):
	for fieldname, label in (
		("custom_van_session", _("Van Session")),
		("custom_van", _("Van")),
		("custom_driver", _("Driver")),
		("payment_type", _("Payment Type")),
		("party_type", _("Party Type")),
		("party", _("Party")),
		("mode_of_payment", _("Mode of Payment")),
	):
		if not doc.get(fieldname):
			frappe.throw(_("{0} is required for Van Payment.").format(label))

	if not is_allowed_van_payment_type(doc):
		frappe.throw(_("Van Payment must be Receive, except refunds against Van Sales Returns must be Pay."))

	if doc.party_type != "Customer":
		frappe.throw(_("Van Payment party type must be Customer."))

	if flt(doc.paid_amount) <= 0 or flt(doc.received_amount) <= 0:
		frappe.throw(_("Van Payment amount must be greater than zero."))


def validate_van_payment_references(doc):
	for row in doc.get("references") or []:
		if row.reference_doctype != "Sales Invoice" or not row.reference_name:
			continue

		invoice = frappe.db.get_value(
			"Sales Invoice",
			row.reference_name,
			["custom_is_van_sale", "custom_van_session"],
			as_dict=True,
		)
		if not invoice or not cint(invoice.custom_is_van_sale):
			frappe.throw(
				_("Van Payment can only be allocated against Van Sales Invoices. Row #{0}: {1}")
				.format(row.idx, frappe.bold(row.reference_name))
			)

		if invoice.custom_van_session != doc.custom_van_session:
			frappe.throw(
				_("Row #{0}: Sales Invoice {1} belongs to Van Session {2}, not {3}.")
				.format(
					row.idx,
					frappe.bold(row.reference_name),
					frappe.bold(invoice.custom_van_session),
					frappe.bold(doc.custom_van_session),
				)
			)


def is_allowed_van_payment_type(doc):
	return doc.payment_type == "Receive" or (doc.payment_type == "Pay" and references_van_return(doc))


def references_van_return(doc):
	for row in doc.get("references") or []:
		if row.reference_doctype != "Sales Invoice" or not row.reference_name:
			continue

		invoice = frappe.db.get_value(
			"Sales Invoice",
			row.reference_name,
			["custom_is_van_sale", "is_return"],
			as_dict=True,
		)
		if invoice and cint(invoice.custom_is_van_sale) and cint(invoice.is_return):
			return True

	return False


def get_payment_entry_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if _is_system_user(user):
		return ""

	if not frappe.db.has_column("Payment Entry", "custom_is_van_payment"):
		return ""

	roles = set(frappe.get_roles(user))
	has_van_role = bool(roles.intersection(VAN_SALES_ROLES))
	has_accounting_role = bool(roles.intersection(ACCOUNTING_ROLES))

	if has_van_role and not has_accounting_role:
		return "`tabPayment Entry`.`custom_is_van_payment` = 1"

	if not has_van_role:
		return "ifnull(`tabPayment Entry`.`custom_is_van_payment`, 0) = 0"

	return ""


def has_payment_entry_permission(doc, ptype=None, user=None):
	return has_van_partition_permission(doc, "Payment Entry", user=user)


def _is_system_user(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in set(frappe.get_roles(user))

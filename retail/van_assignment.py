import frappe
from frappe import _


def is_operator(user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	return user != "Administrator" and "Van Sales User" in roles and not roles.intersection({"Van Sales Manager", "System Manager"})


def setup_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({
		"Driver": [{"fieldname": "custom_van_user", "label": "Van Sales Login", "fieldtype": "Link", "options": "User", "insert_after": "employee"}],
		"Van Session": [{"fieldname": "custom_salesperson", "label": "Salesperson Login", "fieldtype": "Link", "options": "User", "insert_after": "driver_name"}],
	})


def session_condition(user=None):
	if not is_operator(user):
		return ""
	return "`tabVan Session`.custom_salesperson = " + frappe.db.escape(user or frappe.session.user)


def has_session_permission(doc, ptype=None, user=None):
	if is_operator(user) and doc.get("custom_salesperson") != (user or frappe.session.user):
		return False
	return None


def fleet_condition(user=None):
	if not is_operator(user):
		return ""
	return f"`tabVan Fleet`.name in (select van from `tabVan Session` where custom_salesperson = {frappe.db.escape(user or frappe.session.user)} and docstatus < 2)"


def has_fleet_permission(doc, ptype=None, user=None):
	if is_operator(user) and doc.name not in {row.van for row in assigned_sessions(user)}:
		return False
	return None


def assigned_sessions(user=None, active=False):
	filters = {"custom_salesperson": user or frappe.session.user, "docstatus": ["<", 2]}
	if active:
		filters["status"] = "Open"
	return frappe.get_all("Van Session", filters=filters, fields=["name", "van", "van_warehouse"])


def validate_session(doc, method=None):
	old = doc.get_doc_before_save()
	if old and old.docstatus == 1:
		for field in ("van", "van_warehouse", "driver", "session_date"):
			if doc.get(field) != old.get(field):
				frappe.throw(_("Create a new session when changing the van or driver."))
	if is_operator():
		if doc.is_new() or not old or old.custom_salesperson != frappe.session.user:
			frappe.throw(_("A Van Sales Manager must assign your session first."), frappe.PermissionError)
		for field in ("custom_salesperson", "driver", "van", "van_warehouse", "session_date"):
			if doc.get(field) != old.get(field):
				frappe.throw(_("Only a Van Sales Manager can change session assignments."), frappe.PermissionError)
		if old.status in ("Closed", "Cancelled"):
			frappe.throw(_("This session is closed."), frappe.PermissionError)
	elif not doc.get("custom_salesperson") and doc.get("driver"):
		doc.custom_salesperson = frappe.db.get_value("Driver", doc.driver, "custom_van_user")
	if doc.get("custom_salesperson"):
		if not frappe.db.get_value("User", doc.custom_salesperson, "enabled") or "Van Sales User" not in frappe.get_roles(doc.custom_salesperson):
			frappe.throw(_("Salesperson must be an enabled user with the Van Sales User role."))
		if old and old.get("custom_salesperson") and old.custom_salesperson != doc.custom_salesperson:
			frappe.throw(_("Create a new session to change the salesperson; historical assignments must be preserved."))
		if doc.status == "Open" and frappe.db.exists("Van Session", {"custom_salesperson": doc.custom_salesperson, "status": "Open", "docstatus": ["<", 2], "name": ["!=", doc.name]}):
			frappe.throw(_("This salesperson already has an open van session."))
	elif doc.status == "Open":
		frappe.throw(_("Assign a Salesperson Login before opening the session."))


def transaction_condition(doctype, user=None):
	if not is_operator(user):
		return ""
	return f"`tab{doctype}`.custom_van_session in (select name from `tabVan Session` where custom_salesperson = {frappe.db.escape(user or frappe.session.user)})"


def chart_condition():
	from retail.module_access import require
	require("Van Sales")
	if not set(frappe.get_roles()).intersection({"Van Sales User", "Van Sales Manager", "System Manager"}):
		frappe.throw(_("Not permitted to view van sales charts."), frappe.PermissionError)
	frappe.has_permission("Sales Invoice", "read", throw=True)
	return transaction_condition("Sales Invoice") or "1=1"


def check_transaction(doc, user=None):
	if not is_operator(user):
		return True
	return bool(doc.get("custom_van_session") and frappe.db.get_value("Van Session", doc.custom_van_session, "custom_salesperson") == (user or frappe.session.user))


def validate_transaction(doc, method=None):
	from retail.van_permissions import VAN_FLAG_FIELDS
	flag = VAN_FLAG_FIELDS.get(doc.doctype)
	if not flag or doc.doctype == "Customer" or not is_operator():
		return
	old = doc.get_doc_before_save()
	if old and old.get(flag) and (not doc.get(flag) or not check_transaction(old)):
		frappe.throw(_("You cannot remove or change another operator's van assignment."), frappe.PermissionError)
	if not doc.get(flag):
		return
	if not check_transaction(doc):
		frappe.throw(_("This van session is not assigned to you."), frappe.PermissionError)
	if old and old.get("custom_van_session") != doc.get("custom_van_session"):
		frappe.throw(_("The transaction session cannot be changed."), frappe.PermissionError)
	session = frappe.get_doc("Van Session", doc.custom_van_session)
	if session.status != "Open" or session.docstatus == 2:
		frappe.throw(_("Transactions require an open van session."), frappe.PermissionError)
	for field, expected in (("custom_van", session.van), ("custom_van_warehouse", session.van_warehouse), ("custom_driver", session.driver)):
		if doc.meta.has_field(field):
			if doc.get(field) and doc.get(field) != expected:
				frappe.throw(_("Van details must match the assigned session."), frappe.PermissionError)
			doc.set(field, expected)

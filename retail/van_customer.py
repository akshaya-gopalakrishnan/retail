import frappe
from frappe import _

from retail.van_permissions import validate_van_document_access


def validate_van_customer_access(doc, method=None):
	validate_van_document_access(
		doc,
		"Customer",
		_("You are not allowed to create or update Van Customers."),
	)

	# Existing shared van customers remain shared until a manager assigns them.
	# Operators cannot steal another driver's customer through the standard REST API.
	from retail.van_assignment import is_operator
	if is_operator():
		old = doc.get_doc_before_save()
		if old and old.get("custom_van_driver") != doc.get("custom_van_driver"):
			frappe.throw(_("Only a Van Sales Manager can change customer driver assignments."), frappe.PermissionError)
		if doc.get("custom_van_driver") and frappe.db.get_value("Driver", doc.custom_van_driver, "custom_van_user") != frappe.session.user:
			frappe.throw(_("Customer is assigned to another driver."), frappe.PermissionError)

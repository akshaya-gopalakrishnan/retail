import frappe
from frappe.utils import cint


VAN_SALES_ROLES = {"Van Sales User", "Van Sales Manager"}
NORMAL_ROLE_GROUPS = {
	"Sales Invoice": {"Sales User", "Sales Manager", "Sales Master Manager", "Accounts User", "Accounts Manager"},
	"Customer": {"Sales User", "Sales Manager", "Sales Master Manager"},
	"Stock Entry": {"Stock User", "Stock Manager"},
	"Material Request": {"Stock User", "Stock Manager", "Purchase User", "Purchase Manager", "Purchase Master Manager"},
	"Payment Entry": {"Accounts User", "Accounts Manager"},
}
VAN_FLAG_FIELDS = {
	"Sales Invoice": "custom_is_van_sale",
	"Customer": "custom_is_van_customer",
	"Stock Entry": "custom_is_van_stock_entry",
	"Material Request": "custom_is_van_stock_request",
	"Payment Entry": "custom_is_van_payment",
}


def get_sales_invoice_permission_query_conditions(user=None):
	return get_van_partition_permission_query_conditions("Sales Invoice", user=user)


def get_customer_permission_query_conditions(user=None):
	return get_van_partition_permission_query_conditions("Customer", user=user)


def get_stock_entry_permission_query_conditions(user=None):
	return get_van_partition_permission_query_conditions("Stock Entry", user=user)


def get_payment_entry_permission_query_conditions(user=None):
	return get_van_partition_permission_query_conditions("Payment Entry", user=user)


def get_material_request_permission_query_conditions(user=None):
	return get_van_partition_permission_query_conditions("Material Request", user=user)


def has_sales_invoice_permission(doc, ptype=None, user=None):
	return has_van_partition_permission(doc, "Sales Invoice", user=user)


def has_customer_permission(doc, ptype=None, user=None):
	return has_van_partition_permission(doc, "Customer", user=user)


def has_stock_entry_permission(doc, ptype=None, user=None):
	return has_van_partition_permission(doc, "Stock Entry", user=user)


def get_van_partition_permission_query_conditions(doctype, user=None):
	user = user or frappe.session.user
	if _is_system_user(user):
		return ""

	flag_field = VAN_FLAG_FIELDS[doctype]
	if not frappe.db.has_column(doctype, flag_field):
		return ""

	roles = set(frappe.get_roles(user))
	has_van_role = bool(roles.intersection(VAN_SALES_ROLES))
	has_normal_role = bool(roles.intersection(NORMAL_ROLE_GROUPS.get(doctype, set())))
	if doctype != "Customer":
		from retail.van_assignment import transaction_condition
		assignment = transaction_condition(doctype, user)
		if assignment:
			van_condition = f"(`tab{doctype}`.`{flag_field}` = 1 and ({assignment}))"
			return f"(ifnull(`tab{doctype}`.`{flag_field}`, 0) = 0 or {van_condition})" if has_normal_role else van_condition

	if has_van_role and not has_normal_role:
		return f"`tab{doctype}`.`{flag_field}` = 1"

	if not has_van_role:
		return f"ifnull(`tab{doctype}`.`{flag_field}`, 0) = 0"

	return ""


def has_van_partition_permission(doc, doctype, user=None):
	user = user or frappe.session.user
	if _is_system_user(user):
		return None

	flag_field = VAN_FLAG_FIELDS[doctype]
	is_van_doc = cint(doc.get(flag_field))
	if is_van_doc and doctype != "Customer":
		from retail.van_assignment import check_transaction
		if not check_transaction(doc, user):
			return False
	roles = set(frappe.get_roles(user))
	has_van_role = bool(roles.intersection(VAN_SALES_ROLES))
	has_normal_role = bool(roles.intersection(NORMAL_ROLE_GROUPS.get(doctype, set())))

	if is_van_doc and not has_van_role:
		return False

	if not is_van_doc and has_van_role and not has_normal_role:
		return False

	return None


def validate_van_document_access(doc, doctype, message):
	if _is_system_user():
		return

	if cint(doc.get(VAN_FLAG_FIELDS[doctype])) and not set(frappe.get_roles()).intersection(VAN_SALES_ROLES):
		frappe.throw(message, frappe.PermissionError)


def _is_system_user(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in set(frappe.get_roles(user))

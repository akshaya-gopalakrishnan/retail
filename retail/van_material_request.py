import frappe
from frappe import _
from frappe.utils import cint, flt

from retail.van_permissions import NORMAL_ROLE_GROUPS, has_van_partition_permission

VAN_SALES_ROLES = {"Van Sales User", "Van Sales Manager"}
STOCK_ROLES = {"Stock User", "Stock Manager", "System Manager"}


def apply_van_material_request_rules(doc, method=None):
	if not cint(doc.get("custom_is_van_stock_request")):
		validate_non_van_material_request_access()
		return

	validate_van_material_request_access()
	session = apply_van_session_details(doc)
	validate_van_material_request(doc, session)


def validate_non_van_material_request_access():
	if _is_system_user():
		return

	roles = set(frappe.get_roles())
	if roles.intersection(VAN_SALES_ROLES) and not roles.intersection(NORMAL_ROLE_GROUPS["Material Request"]):
		frappe.throw(_("Please use Stock Request from Van Sales for van stock requests."))


def validate_van_material_request_access():
	if _is_system_user():
		return

	if not set(frappe.get_roles()).intersection(VAN_SALES_ROLES):
		frappe.throw(_("You are not allowed to create or update Van Stock Requests."))


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


def validate_van_material_request(doc, session=None):
	if doc.material_request_type != "Material Transfer":
		frappe.throw(_("Van Stock Request must be Material Transfer."))

	for fieldname, label in (
		("custom_van_request_type", _("Van Request Type")),
		("custom_van_session", _("Van Session")),
		("custom_van", _("Van")),
		("custom_van_warehouse", _("Van Warehouse")),
		("custom_driver", _("Driver")),
	):
		if not doc.get(fieldname):
			frappe.throw(_("{0} is required for Van Stock Request.").format(label))

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

	item_rows = [row for row in doc.get("items", []) if row.get("item_code")]
	if not item_rows:
		frappe.throw(_("At least one item is required for Van Stock Request."))

	for row in item_rows:
		if flt(row.get("qty")) <= 0:
			frappe.throw(_("Row #{0}: Qty must be greater than zero for Van Stock Request.").format(row.idx))

		if not row.get("warehouse"):
			row.warehouse = doc.custom_van_warehouse


def get_material_request_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if _is_system_user(user):
		return ""

	if not frappe.db.has_column("Material Request", "custom_is_van_stock_request"):
		return ""

	roles = set(frappe.get_roles(user))
	has_van_role = bool(roles.intersection(VAN_SALES_ROLES))
	has_stock_role = bool(roles.intersection(STOCK_ROLES))

	if has_van_role and not has_stock_role:
		return "`tabMaterial Request`.`custom_is_van_stock_request` = 1"

	if not has_van_role:
		return "ifnull(`tabMaterial Request`.`custom_is_van_stock_request`, 0) = 0"

	return ""


def has_material_request_permission(doc, ptype=None, user=None):
	return has_van_partition_permission(doc, "Material Request", user=user)


def _is_system_user(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in set(frappe.get_roles(user))

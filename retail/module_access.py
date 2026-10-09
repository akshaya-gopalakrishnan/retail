"""Additional POS/Van Sales gates; never grant underlying document permissions."""

from functools import wraps
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.utils import cint

MODULE_ROLES = {
	"POS": {"POS User", "POS Manager", "POS Integration User"},
	"Van Sales": {"Van Sales User", "Van Sales Manager"},
}
VAN_FLAGS = {
	"Sales Invoice": "custom_is_van_sale",
	"Customer": "custom_is_van_customer",
	"Stock Entry": "custom_is_van_stock_entry",
	"Material Request": "custom_is_van_stock_request",
	"Payment Entry": "custom_is_van_payment",
}
POS_EXTRA_REPORTS = {"Cashier Wise Sales", "Counter Wise Sales", "Shift Closing Variance", "Item Group Sales Analysis"}


def allowed(module, user=None):
	user = user or frappe.session.user
	if user == "Administrator" or "Super Admin" in frappe.get_roles(user):
		return True
	if not MODULE_ROLES[module].intersection(frappe.get_roles(user)):
		return False
	return module not in frappe.get_cached_doc("User", user).get_blocked_modules()


def requires(module):
	def decorate(function):
		@wraps(function)
		def wrapped(*args, **kwargs):
			require(module)
			return function(*args, **kwargs)
		return wrapped
	return decorate


def require(module, user=None):
	if not allowed(module, user):
		from retail.access_control import deny_technical_access

		deny_technical_access()


def target_module(doctype=None, page=None, report=None, workspace=None):
	if isinstance(doctype, str) and doctype.startswith("POS "):
		return "POS"
	if isinstance(doctype, str) and doctype in {"Van Fleet", "Van Session"}:
		return "Van Sales"
	if isinstance(page, str) and page in {"point-of-sale", "pos"}:
		return "POS"
	if isinstance(page, str) and (page.startswith("van-") or page == "retail-van-sales-invoice"):
		return "Van Sales"
	if isinstance(report, str):
		if report.startswith("POS ") or report in POS_EXTRA_REPORTS:
			return "POS"
		if report.startswith("Van "):
			return "Van Sales"
	if isinstance(workspace, str):
		from retail.workspace_permissions import WORKSPACE_SIDEBAR_GROUPS
		group = WORKSPACE_SIDEBAR_GROUPS.get(workspace, workspace)
		if group in MODULE_ROLES:
			return group


def document_modules(doc):
	module = target_module(doctype=doc.doctype)
	if module:
		yield module
	if doc.doctype in {"Page", "Report", "Workspace", "Dashboard Chart"}:
		target = {"Page": "page", "Report": "report", "Workspace": "workspace", "Dashboard Chart": "report"}[doc.doctype]
		module = target_module(**{target: doc.name})
		if module:
			yield module
	flag = VAN_FLAGS.get(doc.doctype)
	if flag and cint(doc.get(flag)):
		yield "Van Sales"
	if doc.doctype in {"Sales Invoice", "Payment Entry"} and (
		cint(doc.get("is_pos")) or doc.get("pos_profile") or doc.get("external_pos_reference")
	):
		yield "POS"


def has_permission(doc, ptype=None, user=None, **kwargs):
	if any(not allowed(module, user) for module in document_modules(doc)):
		return False
	return None


def validate_document(doc, method=None):
	for module in document_modules(doc):
		require(module)
	# Do not let an edit remove a protected transaction's identifying flags.
	old = doc.get_doc_before_save()
	if old:
		for module in document_modules(old):
			require(module)


def query_conditions(user=None, doctype=None):
	module = target_module(doctype=doctype)
	if module and not allowed(module, user):
		return "1=0"
	conditions = []
	flag = VAN_FLAGS.get(doctype)
	if flag and not allowed("Van Sales", user) and frappe.db.has_column(doctype, flag):
		conditions.append(f"ifnull(`tab{doctype}`.`{flag}`, 0) = 0")
	if doctype in {"Sales Invoice", "Payment Entry"} and not allowed("POS", user):
		for field in ("is_pos", "pos_profile", "external_pos_reference"):
			if frappe.db.has_column(doctype, field):
				empty = "0" if field == "is_pos" else "''"
				conditions.append(f"ifnull(`tab{doctype}`.`{field}`, {empty}) = {empty}")
	return " and ".join(conditions)


def guard_request():
	"""Run after authentication, including API-key authentication."""
	form = frappe.form_dict
	path = unquote(frappe.request.path)
	path = path.replace("/api/v1/", "/api/", 1)
	method = form.get("cmd") or path.split("/method/", 1)[-1]
	module = None
	if method.startswith(("retail.api.pos_sync.", "erpnext.selling.page.point_of_sale.", "erpnext.accounts.doctype.pos_", "retail.retail_app.doctype.pos_", "retail.pos_privileges.", "retail.retail_app.retail_dashboard.get_pos_")):
		module = "POS"
	elif method.startswith(("retail.van_", "retail.retail_app.retail_dashboard.get_van_")):
		module = "Van Sales"
	if module:
		require(module)
	doctype = form.get("doctype") or form.get("dt")
	if "/api/resource/" in path:
		doctype = path.split("/api/resource/", 1)[1].split("/", 1)[0]
	elif "/api/v2/document/" in path:
		doctype = path.split("/api/v2/document/", 1)[1].split("/", 1)[0]
	page = form.get("page") or form.get("page_name")
	workspace = form.get("workspace")
	if method == "frappe.desk.desk_page.getpage":
		page = form.get("name")
	elif method == "frappe.desk.desktop.get_desktop_page":
		workspace_data = frappe.parse_json(page) if isinstance(page, str) else page
		workspace = (workspace_data or {}).get("name") or (workspace_data or {}).get("title")
		page = None
	module = target_module(
		doctype=doctype,
		page=page,
		report=form.get("report_name") or form.get("chart_name"),
		workspace=workspace,
	)
	if module:
		require(module)


def install():
	for role in sorted(set().union(*MODULE_ROLES.values())):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
	for module in MODULE_ROLES:
		if not frappe.db.exists("Module Def", module):
			frappe.get_doc({"doctype": "Module Def", "module_name": module, "app_name": "retail", "custom": 1}).insert(ignore_permissions=True)
	frappe.clear_cache()

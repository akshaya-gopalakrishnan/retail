"""Shared mobile login. Role Profile classification never grants permissions."""
import frappe

MODULE_ROLES = {
    "sales_order": {"Sales User", "Sales Manager"},
    "van_sales": {"Van Sales User", "Van Sales Manager"},
    "purchase": {"Purchase User", "Purchase Manager"},
}
LOGIN_METHODS = {"login", "frappe.auth.login", "retail.api.auth.login"}


def get_user_module(user):
    if not user or user == "Guest":
        return None
    profile = frappe.db.get_value("User", user, "role_profile_name")
    if not profile:
        return None
    doc = frappe.get_doc("Role Profile", profile)
    explicit = doc.get("custom_app_module")
    if explicit:
        return explicit if explicit in MODULE_ROLES else None
    roles = {row.role for row in doc.roles}
    modules = [module for module, expected in MODULE_ROLES.items() if roles & expected]
    return modules[0] if len(modules) == 1 else None


def login_log_module(incoming):
    """Classify failed attempts too, without returning account metadata to callers."""
    incoming = incoming if isinstance(incoming, dict) else {}
    identifier = incoming.get("usr")
    if not identifier:
        return None
    # Match native login identifiers; ambiguous identifiers must not select a user.
    filters = {"name": identifier}
    users = frappe.get_all("User", filters=filters, pluck="name", limit_page_length=2)
    if not users:
        fields = []
        if frappe.get_system_settings("allow_login_using_user_name"):
            fields.append("username")
        if frappe.get_system_settings("allow_login_using_mobile_number"):
            fields.append("mobile_no")
        if not fields:
            return None
        users = frappe.get_all("User", or_filters={field: identifier for field in fields},
                               pluck="name", limit_page_length=2)
    return get_user_module(users[0]) if len(users) == 1 else None


def get_retail_sidebar_permissions():
    """Return visible Desk menu names as a compact permission snapshot."""
    from retail.workspace_permissions import get_workspace_sidebar_items

    permissions = {}
    for page in get_workspace_sidebar_items().get("pages", []):
        name = page.get("label") or page.get("title") or page.get("name")
        if name:
            permissions[name] = True
    return permissions


@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(usr=None, pwd=None):
    from frappe.auth import LoginManager
    from retail.login_sales_person import get_login_access, get_sales_person_identity

    manager = getattr(frappe.local, "login_manager", None) or LoginManager()
    frappe.form_dict.update(usr=usr, pwd=pwd)
    try:
        if manager.login() is False:
            return {"status": "AuthenticationRequired",
                    "detail": "Complete ERP password reset or two-factor authentication."}
        try:
            user = frappe.session.user
            module = get_user_module(user)
            access = get_login_access()
            # Profile classification is metadata, never a login requirement.
            if not (any(access["permissions"].values())
                    or frappe.has_permission("Purchase Order", "read")):
                frappe.throw("App access is required.", frappe.PermissionError)
            result = dict(status="Success", user=user, app_module=module,
                          **get_sales_person_identity(user), **access,
                          driverid=None, vanid=None, warehouse=None, organizationid=None, sessionid=None)
            if module == "van_sales" and access["permissions"]["van_sales"]:
                from retail.api.van_sales import _context
                ctx = _context(frappe._dict())
                result.update(driverid=ctx.driver.name, vanid=ctx.van.name,
                              warehouse=ctx.warehouse,
                              organizationid=ctx.company,
                              sessionid=ctx.session.name if ctx.session else None)
            result["permissions"] = get_retail_sidebar_permissions()
            return result
        except Exception:
            manager.logout()
            raise
    finally:
        frappe.form_dict.pop("pwd", None)
        # Session hooks also populate these for native/legacy logins. This
        # endpoint returns them in message; keep only that canonical copy.
        for field in ("sales_person_id", "sales_person_name", "roles", "permissions"):
            frappe.local.response.pop(field, None)

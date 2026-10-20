"""Delegate existing User editors within the assigning administrator's access."""
import json
from contextlib import contextmanager

import frappe

from retail.access_control import CUSTOMER_ADMIN, SUPER_ADMIN, is_super_admin, deny_technical_access

MANAGER_FIELD = "retail_access_manager"
SIDEBAR_FIELD = "retail_sidebar_permissions"


def is_customer_admin(user=None):
    user = user or frappe.session.user
    return user != "Guest" and CUSTOMER_ADMIN in frappe.get_roles(user)


def manages(doc, user=None):
    user = user or frappe.session.user
    return bool(is_customer_admin(user) and doc.name != user and (
        doc.get(MANAGER_FIELD) == user or (not doc.get(MANAGER_FIELD) and doc.get("owner") == user)
        or doc.is_new()
    ))


def user_visible(name, user=None):
    user = user or frappe.session.user
    return name == user or manages(frappe.get_doc("User", name), user)


def roles(user=None):
    from frappe.permissions import AUTOMATIC_ROLES
    return set(frappe.get_roles(user or frappe.session.user)) - set(AUTOMATIC_ROLES) - {SUPER_ADMIN}


def blocked_modules(user=None):
    return {row.module for row in frappe.get_cached_doc("User", user or frappe.session.user).get("block_modules", [])}


def sidebar_limit(user=None):
    from retail.sidebar_permissions import selection
    from retail.sidebar_registry import entries
    selected = selection(user)
    return {entry["id"] for entry in entries()} if selected is None else selected


def assignment_changed(doc, previous):
    for field, key in (("roles", "role"), ("block_modules", "module"), ("user_emails", "email_account")):
        if {row.get(key) for row in doc.get(field, [])} != {row.get(key) for row in previous.get(field, [])}:
            return True
    return any((doc.get(field) or "") != (previous.get(field) or "") for field in
               ("role_profile_name", "module_profile", "user_type", SIDEBAR_FIELD, MANAGER_FIELD))


def validate_user(doc, previous):
    """Runs at every document event, including before and after native presets."""
    previous = previous or frappe._dict()
    actor = frappe.session.user
    if not is_customer_admin():
        return False
    if doc.name == actor:
        if assignment_changed(doc, previous):
            deny_technical_access()
        return False
    if previous.get("name"):
        # Authorize the saved ownership, never ownership supplied in a request.
        assigned_manager = previous.get(MANAGER_FIELD)
        if not (assigned_manager == actor or (not assigned_manager and previous.get("owner") == actor)):
            deny_technical_access()
    elif not doc.is_new():
        # Delete events do not necessarily load doc_before_save.
        saved = frappe.db.get_value("User", doc.name, [MANAGER_FIELD, "owner"], as_dict=True)
        if not saved or not (saved.get(MANAGER_FIELD) == actor or (not saved.get(MANAGER_FIELD) and saved.owner == actor)):
            deny_technical_access()
    if doc.get(MANAGER_FIELD) not in (None, "", actor):
        deny_technical_access()
    doc.set(MANAGER_FIELD, actor)
    # Presets must not be a way to add roles or modules beyond the ceiling.
    allowed = roles()
    # Native Employee saving adds this role to the managed linked user.
    # This scope exists only around that server-side operation.
    from retail.employee_permissions import automatic_employee_role_allowed
    if automatic_employee_role_allowed(doc):
        allowed.add("Employee")
    if doc.get("role_profile_name"):
        profile_roles = {row.role for row in frappe.get_doc("Role Profile", doc.role_profile_name).roles}
        if not profile_roles <= allowed:
            deny_technical_access()
    assigned = {row.role for row in doc.get("roles", [])}
    if not assigned <= allowed:
        deny_technical_access()
    blocked = {row.module for row in doc.get("block_modules", [])}
    if doc.get("module_profile"):
        blocked = {row.module for row in frappe.get_doc("Module Profile", doc.module_profile).block_modules}
    required = blocked_modules()
    if not required <= blocked:
        # New users inherit the administrator's module restrictions.
        if previous.get("name") or doc.get("module_profile"):
            deny_technical_access()
        for module in sorted(required - blocked):
            doc.append("block_modules", {"module": module})
    accounts = {row.email_account for row in frappe.get_cached_doc("User", actor).get("user_emails", [])}
    if not {row.email_account for row in doc.get("user_emails", [])} <= accounts:
        deny_technical_access()
    if doc.get("user_type") not in ("System User", "Website User"):
        deny_technical_access()
    if not doc.get(SIDEBAR_FIELD):
        doc.set(SIDEBAR_FIELD, json.dumps({"version": 1, "allowed": sorted(sidebar_limit())}))
    return True


def require_sidebar_assignment(doc):
    if not manages(doc):
        deny_technical_access()
    try:
        data = json.loads(doc.get(SIDEBAR_FIELD) or "null")
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("allowed"), list):
            deny_technical_access()
        if not set(data["allowed"]) <= sidebar_limit():
            deny_technical_access()
    except (ValueError, TypeError):
        deny_technical_access()


def onload(doc, method=None):
    if is_super_admin():
        return
    # The native module editor otherwise receives every installed module.
    if doc.get("__onload") and doc.get("__onload").get("all_modules"):
        doc.set_onload("all_modules", [module for module in doc.get("__onload").all_modules
                                      if module not in blocked_modules()])


@frappe.whitelist()
def get_all_roles():
    from frappe.core.doctype.user.user import get_all_roles as native
    available = native()
    return available if is_super_admin() else sorted(set(available) & roles())


@frappe.whitelist()
def get_perm_info(role):
    from frappe.core.doctype.user.user import get_perm_info as native
    if not is_super_admin() and role not in roles():
        deny_technical_access()
    result = native(role)
    if not is_super_admin():
        from retail.sidebar_permissions import target_allowed
        from retail.access_control import PROTECTED_DOCTYPES
        result = [row for row in result if row.get("parent") not in PROTECTED_DOCTYPES
                  and target_allowed("doctype", row.get("parent"))]
    return result


def apply_ceiling(doc, manager):
    allowed = roles(manager)
    assigned = {row.role for row in doc.roles}
    doc.set("roles", [row for row in doc.roles if row.role in allowed])
    if not assigned <= allowed:
        doc.role_profile_name = None
    required = blocked_modules(manager)
    blocked = {row.module for row in doc.block_modules}
    if required - blocked:
        doc.module_profile = None
        for module in sorted(required - blocked):
            doc.append("block_modules", {"module": module})
    limit = sidebar_limit(manager)
    value = doc.get(SIDEBAR_FIELD)
    try:
        selected = set(json.loads(value)["allowed"]) if value else limit
    except (ValueError, TypeError, KeyError):
        selected = set()
    doc.set(SIDEBAR_FIELD, json.dumps({"version": 1, "allowed": sorted(selected & limit)}, separators=(",", ":")))


@contextmanager
def _staff_sync_administrator():
    """Isolate set_user: it resets the session and user-specific request caches.

    Never call set_user on the browser session object, which is also referenced
    by Session.data and persisted at the end of the request. Restore original
    objects (including form_dict) on both success and failure, also when nested.
    """
    fields = ("session", "cache", "form_dict", "jenv", "role_permissions",
              "new_doc_templates", "user_perms")
    missing = object()
    saved = {field: getattr(frappe.local, field, missing) for field in fields}
    try:
        frappe.local.session = frappe._dict(data=frappe._dict())
        frappe.set_user("Administrator")
        yield
    finally:
        for field, value in saved.items():
            if value is missing:
                if hasattr(frappe.local, field):
                    delattr(frappe.local, field)
            else:
                setattr(frappe.local, field, value)


def sync_children(doc, method=None):
    """Removing an administrator's access also removes it from managed staff."""
    previous = doc.get_doc_before_save()
    if not previous or not assignment_changed(doc, previous):
        return
    with _staff_sync_administrator():
        frappe.clear_cache(user=doc.name)
        children = frappe.get_all("User", filters={MANAGER_FIELD: doc.name}, pluck="name")
        # Adopt older users that this administrator created before delegation existed.
        if CUSTOMER_ADMIN in frappe.get_roles(doc.name):
            children += [row.name for row in frappe.get_all("User", filters={"owner": doc.name}, fields=["name", MANAGER_FIELD]) if not row.get(MANAGER_FIELD)]
        for name in set(children) - {doc.name, "Administrator", "Guest"}:
            if is_super_admin(name):
                continue
            child = frappe.get_doc("User", name)
            child_previous = child.as_dict()
            child.set(MANAGER_FIELD, doc.name)
            apply_ceiling(child, doc.name)
            if child.as_dict() != child_previous:
                child.save(ignore_permissions=True)



def validate_manager(doc, method=None):
    """A Super Admin may attach existing users; reject self/cyclic management."""
    manager = doc.get(MANAGER_FIELD)
    original_manager = manager
    seen = {doc.name}
    while manager:
        if manager in seen:
            frappe.throw(frappe._("A user's access manager cannot form a circular assignment."))
        seen.add(manager)
        manager = frappe.db.get_value("User", manager, MANAGER_FIELD)
    previous = doc.get_doc_before_save()
    # Attaching an existing user must not retain access above their new manager.
    if original_manager and is_super_admin() and SUPER_ADMIN not in {row.role for row in doc.roles} and (
        not previous or previous.get(MANAGER_FIELD) != original_manager
    ):
        apply_ceiling(doc, original_manager)


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    from retail.access_defaults import grant
    create_custom_fields({"User": [{"fieldname": MANAGER_FIELD, "fieldtype": "Link", "options": "User",
        "label": "Managed By", "insert_after": "role_profile_name", "permlevel": 1, "no_copy": 1} ]}, update=True)
    grant("User", CUSTOMER_ADMIN, {"read": 1, "write": 1}, permlevel=1)
    frappe.clear_cache()

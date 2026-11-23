"""Native, editable role presets installed once per site."""

import frappe
from frappe.permissions import rights, setup_custom_perms

from retail.access_control import ACCESS_ADMIN_DOCTYPES, CUSTOMER_ADMIN, SUPER_ADMIN

# Existing staff POS-profile selection and license-repair settings retain their
# separate authorization. Neither grants business document permissions.
CUSTOMER_ADMIN_SETUP_DOCTYPES = {"User", "POS Operator Privilege", "Celesta License Settings"}

BUSINESS_MANAGERS = (
    "Accounts Manager", "Sales Manager", "Purchase Manager", "Stock Manager",
    "HR Manager", "Payroll Manager", "Projects Manager", "Manufacturing Manager",
    "Quality Manager", "Maintenance Manager", "Support Team", "Fleet Manager",
    "POS Manager", "Van Sales Manager",
)
PROFILES = {
    "Super Admin": (SUPER_ADMIN,),
    "Administrator": (CUSTOMER_ADMIN, *BUSINESS_MANAGERS),
    "Store Manager": ("Sales Manager", "Purchase Manager", "Stock Manager", "POS Manager"),
    # Choose the department's functional roles after installation.
    "Department Manager": ("Employee",),
    "Supervisor": ("POS User",),
    "Normal User": ("Employee",),
    "Cashier": ("POS User",),
    "Sales User": ("Sales User",),
    "Purchase User": ("Purchase User",),
    "Stock User": ("Stock User",),
    "Accounts User": ("Accounts User",),
    "HR User": ("HR User",),
    "Van Sales User": ("Van Sales User",),
}


def grant(doctype, role, values, permlevel=0):
    setup_custom_perms(doctype)
    if frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0}):
        return
    frappe.get_doc({
        "doctype": "Custom DocPerm", "parent": doctype, "parenttype": "DocType",
        "parentfield": "permissions", "role": role, "permlevel": permlevel, **values,
    }).insert(ignore_permissions=True)


def install_defaults():
    for role in (SUPER_ADMIN, CUSTOMER_ADMIN):
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
    existing_roles = set(frappe.get_all("Role", pluck="name"))
    for name, roles in PROFILES.items():
        if not frappe.db.exists("Role Profile", name):
            frappe.get_doc({
                "doctype": "Role Profile", "role_profile": name,
                "roles": [{"role": role} for role in dict.fromkeys(roles) if role in existing_roles],
            }).insert(ignore_permissions=True)
    for row in frappe.get_all("DocType", filters={"istable": 0}, fields=["name", "module", "is_submittable", "allow_import"]):
        values = dict.fromkeys(rights, 1)
        values.update(submit=int(bool(row.is_submittable)), cancel=int(bool(row.is_submittable)),
                      amend=int(bool(row.is_submittable)), **{"import": int(bool(row.allow_import))})
        if row.name in ACCESS_ADMIN_DOCTYPES:
            grant(row.name, SUPER_ADMIN, values)
        levels = {int(field.permlevel or 0) for field in frappe.get_meta(row.name).fields} - {0}
        if row.name in ACCESS_ADMIN_DOCTYPES:
            for level in levels:
                grant(row.name, SUPER_ADMIN, {"read": 1, "write": 1}, level)
    # Customer administration uses the ordinary User form, without security fields
    # at permlevel 1 and without System Manager's technical authority.
    grant("User", CUSTOMER_ADMIN, {"read": 1, "write": 1, "create": 1, "delete": 1})
    # Existing module gate roles are intentionally kept separate from integration users.
    for dt in ("POS Invoice", "POS Opening Entry", "POS Closing Entry"):
        if frappe.db.exists("DocType", dt):
            grant(dt, "POS User", {"read": 1, "write": 1, "create": 1, "submit": 1, "print": 1})
    for dt in ("POS Cashier Shift", "POS Counter Session", "POS Branch Day Closing", "POS Profile", "POS Branch Counter"):
        if frappe.db.exists("DocType", dt):
            meta = frappe.get_meta(dt)
            grant(dt, "POS Manager", {"read": 1, "write": 1, "create": 1, "report": 1, "print": 1, "submit": int(bool(meta.is_submittable))})


def restrict_super_admin_to_access_settings():
    """Remove historical blanket grants without changing users or other roles."""
    if not frappe.db.exists("Role", SUPER_ADMIN):
        return
    from frappe.utils import cint
    # Both tables are needed: older Retail fixtures also granted this role POS
    # permissions. No historical transaction or individual role assignment changes.
    changed = set()
    for table in ("Custom DocPerm", "DocPerm"):
        has_ignore_flag = frappe.db.has_column(table, "ignore_user_permissions")
        fields = ["name", "parent"] + (["ignore_user_permissions"] if has_ignore_flag else [])
        for row in frappe.get_all(table, filters={"role": SUPER_ADMIN}, fields=fields):
            if row.parent not in ACCESS_ADMIN_DOCTYPES:
                frappe.db.delete(table, {"name": row.name, "role": SUPER_ADMIN})
                changed.add(row.parent)
            elif has_ignore_flag and cint(row.ignore_user_permissions):
                frappe.db.set_value(table, row.name, "ignore_user_permissions", 0, update_modified=False)
                changed.add(row.parent)
    # Install only native permissions needed by the protected permission editor.
    for name in sorted(ACCESS_ADMIN_DOCTYPES):
        if not frappe.db.exists("DocType", name) or frappe.get_meta(name).istable:
            continue
        grant(name, SUPER_ADMIN, {"read": 1, "write": 1, "create": 1, "delete": 1,
                                 "report": 1, "export": 1})
        for level in {int(field.permlevel or 0) for field in frappe.get_meta(name).fields} - {0}:
            grant(name, SUPER_ADMIN, {"read": 1, "write": 1}, level)
        changed.add(name)
    for name in changed:
        frappe.clear_cache(doctype=name)


def restrict_customer_admin_to_staff_management():
    """Delegation authority must not silently grant accounting/business rights."""
    if not frappe.db.exists("Role", CUSTOMER_ADMIN):
        return
    changed = set()
    for table in ("Custom DocPerm", "DocPerm"):
        for row in frappe.get_all(table, filters={"role": CUSTOMER_ADMIN}, fields=["name", "parent"]):
            if row.parent not in CUSTOMER_ADMIN_SETUP_DOCTYPES:
                frappe.db.delete(table, {"name": row.name, "role": CUSTOMER_ADMIN})
                changed.add(row.parent)
    grant("User", CUSTOMER_ADMIN, {"read": 1, "write": 1, "create": 1, "delete": 1})
    grant("User", CUSTOMER_ADMIN, {"read": 1, "write": 1}, permlevel=1)
    for name in changed | {"User"}:
        frappe.clear_cache(doctype=name)
    # Cached can_read lists and Awesome Bar boot data otherwise retain old grants.
    for user in frappe.get_all("Has Role", filters={"role": CUSTOMER_ADMIN, "parenttype": "User"}, pluck="parent"):
        frappe.clear_cache(user=user)

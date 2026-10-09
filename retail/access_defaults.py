"""Native, editable role presets installed once per site."""

import frappe
from frappe.permissions import AUTOMATIC_ROLES, rights, setup_custom_perms

from retail.access_control import CUSTOMER_ADMIN, PROTECTED_DOCTYPES, SUPER_ADMIN, TECHNICAL_MODULES

BUSINESS_MANAGERS = (
    "Accounts Manager", "Sales Manager", "Purchase Manager", "Stock Manager",
    "HR Manager", "Payroll Manager", "Projects Manager", "Manufacturing Manager",
    "Quality Manager", "Maintenance Manager", "Support Team", "Fleet Manager",
    "POS Manager", "Van Sales Manager",
)
PROFILES = {
    "Super Admin": (SUPER_ADMIN, "System Manager", *BUSINESS_MANAGERS),
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
        if name == "Super Admin":
            roles = sorted(set(frappe.get_all("Role", filters={"disabled": 0}, pluck="name")) - set(AUTOMATIC_ROLES))
        if not frappe.db.exists("Role Profile", name):
            frappe.get_doc({
                "doctype": "Role Profile", "role_profile": name,
                "roles": [{"role": role} for role in dict.fromkeys(roles) if role in existing_roles],
            }).insert(ignore_permissions=True)
    for row in frappe.get_all("DocType", filters={"istable": 0}, fields=["name", "module", "is_submittable", "allow_import"]):
        values = dict.fromkeys(rights, 1)
        values.update(submit=int(bool(row.is_submittable)), cancel=int(bool(row.is_submittable)),
                      amend=int(bool(row.is_submittable)), **{"import": int(bool(row.allow_import))})
        grant(row.name, SUPER_ADMIN, {**values, "ignore_user_permissions": 1})
        levels = {int(field.permlevel or 0) for field in frappe.get_meta(row.name).fields} - {0}
        for level in levels:
            grant(row.name, SUPER_ADMIN, {"read": 1, "write": 1}, level)
        if row.module not in TECHNICAL_MODULES and row.name not in PROTECTED_DOCTYPES:
            grant(row.name, CUSTOMER_ADMIN, values)
            for level in levels:
                grant(row.name, CUSTOMER_ADMIN, {"read": 1, "write": 1}, level)
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

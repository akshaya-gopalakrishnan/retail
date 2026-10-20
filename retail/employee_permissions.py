"""Scoped delegation of Employee's automatic User Permission records."""
from contextvars import ContextVar

import frappe
from erpnext.setup.doctype.employee.employee import Employee

from retail.access_control import deny_technical_access, is_protected_user, is_super_admin
from retail.delegated_access import is_customer_admin, manages

_permission_scope = ContextVar("retail_employee_permission_scope", default=None)


def automatic_permission_allowed(doc):
    scope = _permission_scope.get()
    return bool(scope and doc.doctype == "User Permission" and
                (frappe.session.user, doc.user, doc.allow, doc.for_value) in scope and
                not doc.get("applicable_for") and doc.get("apply_to_all_doctypes") == 1 and
                not doc.get("is_default") and not doc.get("hide_descendants"))


def require_managed_employee(employee):
    from retail.sidebar_permissions import target_allowed
    if not target_allowed("doctype", "Employee"):
        deny_technical_access()
    employee.check_permission("create" if employee.flags.in_insert or employee.is_new() else "write")
    previous = employee.get_doc_before_save()
    for record in (previous, employee):
        if not record:
            continue
        for user in {record.get("user_id"), record.get("pos_login_user")} - {None, ""}:
            if is_protected_user(user) or not manages(frappe.get_doc("User", user)):
                deny_technical_access()


def prepare_employee(doc, method=None):
    """Delegate the automatic-permission operation, preserving the site controller."""
    if is_customer_admin() and not is_super_admin():
        if doc.get("user_id") or doc.get("pos_login_user"):
            require_managed_employee(doc)
        from types import MethodType
        doc.update_user_permissions = MethodType(update_user_permissions, doc)


def update_user_permissions(self):
    if is_super_admin() or not is_customer_admin():
        return Employee.update_user_permissions(self)
    if not self.has_value_changed("user_id") and not self.has_value_changed("create_user_permission"):
        return
    require_managed_employee(self)
    scope = {(frappe.session.user, self.user_id, allow, value)
             for allow, value in (("Employee", self.name), ("Company", self.company))}
    token = _permission_scope.set(scope)
    try:
        exists = frappe.db.exists("User Permission", {
            "user": self.user_id, "allow": "Employee", "for_value": self.name})
        if not exists and self.create_user_permission:
            from frappe.permissions import add_user_permission
            add_user_permission("Employee", self.name, self.user_id, ignore_permissions=True)
            add_user_permission("Company", self.company, self.user_id, ignore_permissions=True)
        elif exists and not self.create_user_permission:
            # Match native behavior, with the same narrowly scoped guard.
            for allow, value in (("Employee", self.name), ("Company", self.company)):
                name = frappe.db.get_value("User Permission", {
                    "user": self.user_id, "allow": allow, "for_value": value})
                if name:
                    frappe.delete_doc("User Permission", name, ignore_permissions=True)
    finally:
        _permission_scope.reset(token)

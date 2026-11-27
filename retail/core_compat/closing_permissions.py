"""Keep employee self-service restrictions out of manager day-closing reads."""
from contextvars import ContextVar
from functools import wraps

import frappe

_employee_exemption = ContextVar('retail_closing_employee_exemption', default=None)
MANAGER_ROLES = frozenset({'Admin', 'Customer Administrator', 'Customer Manager', 'System Manager'})


def install(*args, **kwargs):
    import frappe.permissions as permissions
    from frappe.core.doctype.user_permission import user_permission as rules

    if getattr(permissions.has_user_permission, '_retail_closing_manager', False):
        return
    original_check = permissions.has_user_permission
    original_rules = rules.get_user_permissions

    @wraps(original_rules)
    def get_user_permissions(user=None):
        result = original_rules(user)
        if _employee_exemption.get() == (user or frappe.session.user):
            # Copy; never remove Employee restrictions from shared/cached rules.
            return frappe._dict((key, value) for key, value in result.items() if key != 'Employee')
        return result

    @wraps(original_check)
    def has_user_permission(doc, user=None, debug=False, ptype=None):
        actor = user or frappe.session.user
        exempt = (doc.doctype == 'POS Branch Day Closing'
            and 'retail' in frappe.get_installed_apps()
            and bool(MANAGER_ROLES.intersection(frappe.get_roles(actor))))
        if not exempt:
            return original_check(doc, user=user, debug=debug, ptype=ptype)
        token = _employee_exemption.set(actor)
        try:
            return original_check(doc, user=user, debug=debug, ptype=ptype)
        finally:
            _employee_exemption.reset(token)

    has_user_permission._retail_closing_manager = True
    rules.get_user_permissions = get_user_permissions
    permissions.has_user_permission = has_user_permission

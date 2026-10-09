"""Contact guidance for native ERP permission popups; never change authorization."""

import json
from urllib.parse import unquote

import frappe
from frappe import _

from retail.access_control import (
    CUSTOMER_ADMIN, PROTECTED_DOCTYPES, TECHNICAL_EDIT_DOCTYPES,
    TECHNICAL_MODULES, is_protected_user, is_super_admin,
)


def request_target(request):
    form = frappe.form_dict
    dt = form.get("doctype") or form.get("dt")
    name = form.get("name") or form.get("docname")
    path = unquote(request.path).replace("/api/v1/", "/api/", 1)
    action = form.get("action") or form.get("method") or ""
    permission = "read"
    for route in ("/api/resource/", "/api/v2/document/"):
        if route in path:
            parts = path.split(route, 1)[1].split("/")
            dt = parts[0]
            name = parts[1] if len(parts) > 1 else None
            permission = {"DELETE": "delete", "PUT": "write", "PATCH": "write", "POST": "write" if name else "create"}.get(request.method, "read")
    payload = form.get("doc") or form.get("docs")
    if payload:
        try:
            payload = json.loads(payload) if isinstance(payload, str) else payload
        except (TypeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            dt = payload.get("doctype") or dt
            name = payload.get("name") or name
            permission = "create" if payload.get("__islocal") or not name else "write"
    command = form.get("cmd") or path.rsplit("/", 1)[-1]
    action = str(action or command.rsplit(".", 1)[-1]).lower()
    if action in ("submit", "cancel", "delete", "amend", "print", "export"):
        permission = action
    elif action in ("set_value", "save", "savedocs", "update", "bulk_update"):
        permission = "write"
    elif action in ("insert", "create_doc"):
        permission = "create"
    elif action in ("get", "getdoc", "get_list", "get_value", "get_count", "run"):
        permission = "read"
    if not dt and form.get("report_name"):
        dt = frappe.db.get_value("Report", form.report_name, "ref_doctype")
    return dt, name, permission


def company_administrator_can_help(request):
    # A customer administrator must not be directed back to themselves.
    if frappe.session.user == "Guest" or CUSTOMER_ADMIN in frappe.get_roles():
        return False
    if frappe.flags.get("retail_technical_permission_denied"):
        return False
    dt, name, permission = request_target(request)
    if not isinstance(dt, str) or dt in PROTECTED_DOCTYPES:
        return False
    if dt in TECHNICAL_EDIT_DOCTYPES and permission not in ("read", "print", "export"):
        return False
    if dt == "User" and is_protected_user(name):
        return False
    if not frappe.db.exists("DocType", dt):
        return False
    if dt != "User" and frappe.get_meta(dt).module in TECHNICAL_MODULES:
        return False
    admins = frappe.get_all("Has Role", filters={"parenttype": "User", "role": CUSTOMER_ADMIN}, pluck="parent")
    if not admins:
        return False
    admins = frappe.get_all("User", filters={"name": ["in", admins], "enabled": 1}, pluck="name")
    for admin in admins:
        if is_super_admin(admin):
            continue
        # Check the actual document when possible, respecting branch/user scopes.
        target = name if isinstance(name, str) and permission != "create" and frappe.db.exists(dt, name) else None
        if frappe.has_permission(dt, permission, doc=target, user=admin, throw=False):
            return True
    return False


def after_request(response, request):
    if response is None or response.status_code != 403 or not response.is_json:
        return
    payload = response.get_json(silent=True)
    if not isinstance(payload, dict):
        return
    v2 = isinstance(payload.get("errors"), list)
    is_permission_error = payload.get("exc_type") == "PermissionError" or (
        v2 and any(error.get("type") == "PermissionError" for error in payload["errors"] if isinstance(error, dict))
    )
    if not is_permission_error or is_super_admin():
        return
    if company_administrator_can_help(request):
        message = _("You do not have permission to perform this action. Please contact your company administrator.")
    else:
        message = _("You do not have permission to perform this action. Please contact the software team.")
    title = _("Permission Required")
    # Development-mode tracebacks and native required-role lists can reveal
    # internal role names. Keep the native error schema, not those details.
    if v2:
        payload = {"errors": [{"type": "PermissionError", "message": message, "title": title}]}
    else:
        payload = {"exc_type": "PermissionError", "exception": "frappe.exceptions.PermissionError: " + message,
                   "_server_messages": json.dumps([json.dumps({"message": message, "title": title, "indicator": "red"})])}
    response.set_data(json.dumps(payload))

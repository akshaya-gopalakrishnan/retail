"""Sanitized API payloads, including authentication failures before dispatch."""
import json

import frappe
from retail.access_control import is_super_admin


METHODS = {
    "retail.api.pos_sync.get_sales_order_data",
    "retail.api.pos_sync.save_sales_order",
}


def sanitize_payload(value):
    """Keep business data while excluding credentials and server tracebacks."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            sensitive = any(part in normalized for part in (
                "password", "passwd", "secret", "token", "authorization", "cookie",
            )) or normalized in {"pwd", "sid", "api_key", "exc", "exception", "traceback"}
            result[key] = "[REDACTED]" if sensitive else sanitize_payload(item)
        return result
    if isinstance(value, (list, tuple)):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, str):
        # Frappe clients commonly send `data` as an encoded JSON string.
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return value
        if isinstance(decoded, (dict, list)):
            return sanitize_payload(decoded)
    return value


def has_permission(doc, ptype=None, user=None, **kwargs):
    return is_super_admin(user) and ptype in (None, "read", "select", "report")


def query_conditions(user=None):
    return "" if is_super_admin(user) else "1=0"


def after_request(request, response):
    if response is None:
        return
    form = getattr(frappe.local, "form_dict", {}) or {}
    method = form.get("cmd") or request.path.removeprefix("/api/method/")
    login = method in ("login", "frappe.auth.login")
    customer = method == "retail.api.pos_sync.upsert_customer"
    data = form.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    if not (login or method in METHODS or (customer and (form.get("context") or data.get("context")) == "sales_order")):
        return
    # Login is shared by Desk/POS/Sales Order; capture all logins rather than
    # pretending failed authentication can identify the calling application.
    payload = response.get_json(silent=True) if response.is_json else {}
    payload = payload if isinstance(payload, dict) else {}
    try:
        incoming = request.get_json(silent=True) if request.is_json else None
        if incoming is None:
            incoming = dict(form)
        frappe.get_doc({
            "doctype": "Sales Order API Log",
            "operation": "Login (shared)" if login else method.rsplit(".", 1)[-1],
            "user": str(form.get("usr") or "")[:140] if login else frappe.session.user,
            "status": "Failed" if response.status_code >= 400 else "Success",
            "http_status": response.status_code,
            "endpoint": method[:140],
            "error_type": str(payload.get("exc_type") or "")[:140],
            "request_json": json.dumps(sanitize_payload(incoming), indent=2, default=str),
            "response_json": json.dumps(sanitize_payload(response.get_json(silent=True) if response.is_json else {
                "http_status": response.status_code,
                "content_type": response.content_type,
            }), indent=2, default=str),
        }).insert(ignore_permissions=True)
        # Frappe already committed/rolled back the business request before this hook.
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.logger().exception("Could not save Sales Order API diagnostics")

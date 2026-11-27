"""Sanitized API payloads, including authentication failures before dispatch."""
import json
from html import unescape

import frappe
from retail.access_control import is_super_admin
from retail.api.auth import LOGIN_METHODS, login_log_module


METHODS = {
    "retail.api.pos_sync.get_sales_order_data",
    "retail.api.pos_sync.save_sales_order",
}


def response_issue(body, http_status):
    """Extract client-facing diagnostics, never the server traceback."""
    from frappe.utils import strip_html

    body = body if isinstance(body, dict) else {}
    message = body.get("message")
    detail = message if isinstance(message, dict) else {}
    failed = http_status >= 400 or detail.get("status") in {"Failed", "Error"}
    pending = detail.get("status") == "AuthenticationRequired"
    if not (failed or pending):
        return ""
    texts = []

    def collect(value):
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except (ValueError, TypeError):
                text = unescape(strip_html(value)).strip()
                if text and text not in texts:
                    texts.append(text)
            else:
                if isinstance(decoded, (dict, list)):
                    collect(decoded)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key in ("detail", "error", "message"):
                if value.get(key):
                    collect(value[key])

    collect(body.get("_server_messages"))
    collect(message)
    collect(body.get("error"))
    return "\n".join(texts)[:4000] or str(body.get("exc_type") or f"HTTP {http_status}")[:140]


def sanitize_payload(value):
    """Keep business data while excluding credentials and server tracebacks."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            sensitive = any(part in normalized for part in (
                "password", "passwd", "secret", "token", "authorization", "cookie",
            )) or normalized in {"pwd", "sid", "api_key", "exc", "exception", "traceback",
                "otp", "tmp_id", "pin", "pin_code", "quick_pin", "quick_pin_hash", "quick_pin_salt"}
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
    method = form.get("cmd") or request.path.replace("/api/v1/", "/api/", 1).removeprefix("/api/method/")
    login = method in LOGIN_METHODS
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
    payload = response.get_json(silent=True) if response.is_json else {}
    payload = payload if isinstance(payload, dict) else {}
    try:
        incoming = request.get_json(silent=True) if request.is_json else None
        if incoming is None:
            incoming = dict(form)
        if login and login_log_module(incoming) != "sales_order":
            return
        frappe.get_doc({
            "doctype": "Sales Order API Log",
            "operation": "Login" if login else method.rsplit(".", 1)[-1],
            "user": str(form.get("usr") or (incoming.get("usr") if isinstance(incoming, dict) else "") or "")[:140] if login else frappe.session.user,
            "status": "Failed" if response.status_code >= 400 or (
                isinstance(payload.get("message"), dict) and payload["message"].get("status") in {"Failed", "Error"}
            ) else "Pending" if isinstance(payload.get("message"), dict) and payload["message"].get("status") == "AuthenticationRequired" else "Success",
            "http_status": response.status_code,
            "endpoint": method[:140],
            "error_type": str(payload.get("exc_type") or "")[:140],
            "error_message": response_issue(payload, response.status_code),
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


def extend_bootinfo(bootinfo):
    """Register the log's Desk route only for users already allowed to read it.

    Native boot discovers DocTypes from role-permission rows. This restricted
    log has no default rows, so even Administrator's permitted List route was
    missing. This updates client discovery, not server-side permissions.
    """
    if not is_super_admin() or not frappe.has_permission("Sales Order API Log", "read"):
        return
    for key in ("can_read", "all_read"):
        values = bootinfo.user.setdefault(key, [])
        if "Sales Order API Log" not in values:
            values.append("Sales Order API Log")

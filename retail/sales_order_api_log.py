"""Secret-free request diagnostics, including authentication failures before dispatch."""
import json

import frappe
from retail.access_control import is_super_admin


METHODS = {
    "retail.api.pos_sync.get_sales_order_data",
    "retail.api.pos_sync.save_sales_order",
}


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
    summary = {"http_status": response.status_code, "error_type": payload.get("exc_type")}
    # Never persist bodies, headers, cookies, tokens, passwords or tracebacks.
    try:
        frappe.get_doc({
            "doctype": "Sales Order API Log",
            "operation": "Login (shared)" if login else method.rsplit(".", 1)[-1],
            "user": str(form.get("usr") or "")[:140] if login else frappe.session.user,
            "status": "Failed" if response.status_code >= 400 else "Success",
            "http_status": response.status_code,
            "endpoint": method[:140],
            "error_type": str(payload.get("exc_type") or "")[:140],
            "request_json": json.dumps({"method": request.method, "endpoint": method}),
            "response_json": json.dumps(summary, indent=2),
        }).insert(ignore_permissions=True)
        # Frappe already committed/rolled back the business request before this hook.
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.logger().exception("Could not save Sales Order API diagnostics")

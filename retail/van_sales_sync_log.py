"""Van RPC diagnostics, separate from durable idempotency receipts."""
import json

import frappe
from frappe.utils import now_datetime

from retail.api.auth import LOGIN_METHODS, login_log_module
from retail.module_access import VAN_MOBILE_ALIASES
from retail.sales_order_api_log import sanitize_payload, response_issue


def is_van_method(method):
	return isinstance(method, str) and (method.startswith("retail.api.van_sales.") or
		method == "retail.van_stock.get_van_warehouse_stock" or (
		method.startswith("retail.api.pos_sync.") and method.rsplit(".", 1)[-1] in VAN_MOBILE_ALIASES
	))


def response_status(response, body):
	message = body.get("message") if isinstance(body, dict) else None
	message = message if isinstance(message, dict) else {}
	if response.status_code >= 400 or message.get("status") in {"Failed", "Error"}:
		return "Failed"
	if message.get("status") == "AuthenticationRequired":
		return "Pending"
	return "Duplicate" if message.get("duplicate") or message.get("status") == "Duplicate" else "Success"


def after_request(request, response):
	if response is None:
		return
	form = getattr(frappe.local, "form_dict", {}) or {}
	method = form.get("cmd") or request.path.replace("/api/v1/", "/api/", 1).removeprefix("/api/method/")
	shared_login = method in LOGIN_METHODS
	if not (shared_login or is_van_method(method)):
		return
	try:
		incoming = request.get_json(silent=True) if request.is_json else None
		if incoming is None:
			incoming = dict(form)
		if shared_login and login_log_module(incoming) != "van_sales":
			return
		clean = sanitize_payload(incoming)
		values = dict(clean) if isinstance(clean, dict) else {}
		data = values.get("data")
		if isinstance(data, dict):
			values = {**data, **values}
		body = response.get_json(silent=True) if response.is_json else {}
		body = body if isinstance(body, dict) else {}
		message = body.get("message") or {}
		message = message if isinstance(message, dict) else {}
		session = message.get("session") or {}
		session = session if isinstance(session, dict) else {}
		def field(*keys):
			return str(next((source[key] for source in (values, message, session)
				for key in keys if source.get(key) is not None), ""))[:140]
		login = shared_login or method.rsplit(".", 1)[-1] == "driver_login"
		stamp = now_datetime()
		record = {
			"name": frappe.generate_hash(length=20),
			"creation": stamp, "modified": stamp,
			"owner": frappe.session.user, "modified_by": frappe.session.user,
			"docstatus": 0, "idx": 0,
			"operation": "Login" if shared_login else method.rsplit(".", 1)[-1][:140],
			"user": field("userid", "usr") if login else frappe.session.user,
			"status": response_status(response, body),
			"http_status": response.status_code,
			"request_id": field("requestid", "request_id"),
			"session_id": field("sessionid", "session_id"),
			"driver_id": field("driverid", "driver_id"),
			"endpoint": method[:140],
			"error_type": str(body.get("exc_type") or "")[:140],
			"error_message": response_issue(body, response.status_code),
			"request_json": json.dumps(clean, indent=2, default=str),
			"response_json": json.dumps(sanitize_payload(body if response.is_json else {
				"http_status": response.status_code, "content_type": response.content_type,
			}), indent=2, default=str),
		}
		# Fixed audit fields only. Bypass document validation, which correctly
		# denies Van documents to Guest/disabled users: those denied requests
		# must still be recorded. This grants no reader or writer permissions.
		frappe.db.bulk_insert("Van Sales Sync Log", fields=list(record), values=[tuple(record.values())])
		# Business request has already committed/rolled back. Audit only this call.
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.logger().exception("Could not save Van Sales sync diagnostics")

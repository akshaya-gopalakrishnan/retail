"""Serve a temporary browser test session; never alter existing user access."""
import os
import json
from urllib.parse import quote
import subprocess
import threading
import uuid
from pathlib import Path

import frappe
from frappe.app import application_with_statics
from frappe.sessions import Session, delete_session, clear_sessions
from werkzeug.serving import make_server, WSGIRequestHandler

BENCH = Path(__file__).resolve().parents[3]
os.chdir(BENCH / "sites")
frappe.init(site="retail-test.localhost")
frappe.connect()
frappe.set_user("Administrator")
user = "sidebar-browser-" + uuid.uuid4().hex[:8] + "@example.invalid"
sid = None
operator_sid = None
server = None
try:
    frappe.get_doc({"doctype": "User", "email": user, "first_name": "Sidebar Browser Regression",
                    "send_welcome_email": 0, "user_type": "System User",
                    "roles": [{"role": "Sales User"}, {"role": "Accounts User"}]}).insert(ignore_permissions=True)
    frappe.local.request = frappe._dict(cookies={})
    frappe.local.request_ip = "127.0.0.1"
    frappe.local.form_dict = frappe._dict()
    session = Session(user="Administrator", user_type="System User", full_name="Administrator")
    sid = session.sid
    operator_sid = Session(user=user, user_type="System User", full_name="Sidebar Browser Regression").sid
    frappe.db.commit()
    class Quiet(WSGIRequestHandler):
        def log(self, *args, **kwargs):
            pass
    browser_url = os.environ.get("RETAIL_BROWSER_URL")
    if not browser_url:
        server = make_server("127.0.0.1", 0, application_with_statics(), threaded=True, request_handler=Quiet)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser_url = "http://retail-test.localhost:" + str(server.server_port)
    environment = dict(os.environ, RETAIL_SID=sid, RETAIL_OPERATOR_SID=operator_sid, RETAIL_USER=user,
                       LD_LIBRARY_PATH="/tmp/retail-sidebar-browser-libs/extracted/usr/lib/x86_64-linux-gnu",
                       RETAIL_URL=browser_url)
    if os.environ.get("RETAIL_MENU_AUDIT") == "1":
        from retail.sidebar_registry import entries
        audit_routes = [frappe.scrub(entry["workspace"]).replace("_", "-") for entry in entries()]
        for doctype in ('Item', 'Customer', 'Sales Invoice', 'Purchase Invoice', 'Stock Entry'):
            records = frappe.get_all(doctype, pluck='name', limit=1)
            if records:
                audit_routes.append(frappe.scrub(doctype).replace('_', '-') + '/' + quote(records[0], safe=''))
        environment['RETAIL_AUDIT_ROUTES'] = json.dumps(audit_routes)
    result = subprocess.run(["node", str(Path(__file__).with_suffix(".cjs"))], env=environment,
                            timeout=400 if os.environ.get("RETAIL_MENU_AUDIT") == "1" else 160)
    if result.returncode:
        raise RuntimeError("Browser regression failed")
finally:
    if server:
        server.shutdown()
    frappe.init(site="retail-test.localhost", force=True)
    frappe.connect()
    frappe.set_user("Administrator")
    if sid:
        delete_session(sid=sid, reason="Temporary regression complete")
    if operator_sid:
        delete_session(sid=operator_sid, reason="Temporary regression complete")
    clear_sessions(user)
    if frappe.db.exists("User", user):
        frappe.delete_doc("User", user, ignore_permissions=True, force=True)
    frappe.db.commit()
    frappe.destroy()

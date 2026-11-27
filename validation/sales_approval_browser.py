"""Read-only Chromium check on unsaved forms; no business documents are saved."""
import os
import subprocess
import threading
from pathlib import Path

import frappe
from frappe.app import application_with_statics
from frappe.sessions import Session, delete_session
from werkzeug.serving import make_server, WSGIRequestHandler

BENCH = Path(__file__).resolve().parents[3]
os.chdir(BENCH / 'sites')
frappe.init(site='retail-test.localhost')
frappe.connect()
browser_user = os.environ.get('RETAIL_BROWSER_USER', 'Administrator')
frappe.set_user(browser_user)
sid = None
server = None
try:
    frappe.local.request = frappe._dict(cookies={})
    frappe.local.request_ip = '127.0.0.1'
    frappe.local.form_dict = frappe._dict()
    sid = Session(user=browser_user, user_type='System User', full_name=browser_user).sid
    frappe.db.commit()
    class Quiet(WSGIRequestHandler):
        def log(self, *args, **kwargs):
            pass
    server = make_server('127.0.0.1', 0, application_with_statics(), threaded=True, request_handler=Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
        env=dict(os.environ, RETAIL_URL='http://retail-test.localhost:' + str(server.server_port), RETAIL_SID=sid), timeout=150)
    if result.returncode:
        raise RuntimeError('Sales Invoice approval browser verification failed')
finally:
    if server:
        server.shutdown()
    frappe.init(site='retail-test.localhost', force=True)
    frappe.connect()
    if sid:
        delete_session(sid=sid, reason='Sales Invoice approval browser check complete')
    frappe.db.commit()
    frappe.destroy()

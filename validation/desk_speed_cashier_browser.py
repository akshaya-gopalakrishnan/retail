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
frappe.set_user('Administrator')
user = frappe.db.sql("select distinct u.name from tabUser u inner join `tabHas Role` r on r.parent=u.name where r.role='POS User' and u.enabled=1 and u.user_type='System User' and u.name != 'Administrator' and not exists (select 1 from `tabHas Role` a where a.parent=u.name and a.role in ('Super Admin','System Manager')) order by u.name limit 1")[0][0]
sid = None
server = None
try:
    frappe.local.request = frappe._dict(cookies={})
    frappe.local.request_ip = '127.0.0.1'
    frappe.local.form_dict = frappe._dict()
    sid = Session(user=user, user_type='System User', full_name=frappe.db.get_value('User',user,'full_name')).sid
    frappe.db.commit()
    class Quiet(WSGIRequestHandler):
        def log(self, *args, **kwargs):
            pass
    server = make_server('127.0.0.1', 0, application_with_statics(), threaded=True, request_handler=Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
        env=dict(os.environ, RETAIL_URL='http://retail-test.localhost:' + str(server.server_port), RETAIL_SID=sid), timeout=300)
    if result.returncode:
        raise RuntimeError('Desk speed browser verification failed')
finally:
    if server:
        server.shutdown()
    frappe.init(site='retail-test.localhost', force=True)
    frappe.connect()
    if sid:
        delete_session(sid=sid, reason='Desk speed browser check complete')
    frappe.db.commit()
    frappe.destroy()

"""Read-only local Desk audit; only an ephemeral Redis session is created.

Uses an existing test-site user with an in-memory sidebar overlay. No saved User
or business changes; mutating browser requests are blocked by this local server.
Run from sites with ../env/bin/python ../apps/retail/validation/accounting_permissions_browser.py.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import threading
from unittest.mock import patch

import frappe
from frappe.app import application_with_statics
from frappe.utils import now
from werkzeug.serving import WSGIRequestHandler, make_server

SITE = 'retail-test.localhost'
USER = os.environ.get('RETAIL_BROWSER_USER', 'cashier@gmail.com')
frappe.init(site=SITE)
frappe.connect()
from retail.sidebar_registry import registry
user = copy.deepcopy(frappe.get_cached_doc('User', USER))
allowed = [entry['id'] for group in registry() if group['workspace'] != 'Accounts'
           for entry in [group, *group['children']] if entry['workspace'] != 'Accounts Reports']
if os.environ.get('RETAIL_TEST_AWESOME_BAR') == '0':
    allowed = [key for key in allowed if key != 'control:awesome_bar']
user.retail_sidebar_permissions = json.dumps({'version': 1, 'allowed': allowed})
user.module_profile = None
user.set('block_modules', [])
user.append('block_modules', {'module': 'Accounts'})
original = frappe.get_cached_doc

def cached(doctype, name=None, *args, **kwargs):
    if doctype == 'User' and name == USER:
        return copy.deepcopy(user)
    return original(doctype, name, *args, **kwargs)

sid = frappe.generate_hash(length=48)
stamp = now()
frappe.cache.hset('session', sid, frappe._dict(user=USER, sid=sid, data=frappe._dict(
    user=USER, last_updated=stamp, creation=stamp, session_expiry='06:00:00',
    full_name=user.full_name, user_type='System User', csrf_token=frappe.generate_hash())))
frappe.cache.hset('last_db_session_update', sid, stamp)
frappe.clear_cache(user=USER)
app = application_with_statics()

def read_only(environ, start_response):
    path = environ.get('PATH_INFO', '')
    if any(token in path for token in ('.save', '.delete', '.insert', '.set_', '.update_', '.mark_', 'run_doc_method', 'logout')):
        start_response('405 Method Not Allowed', [('Content-Type', 'text/plain')])
        return [b'Read-only local audit']
    return app(environ, start_response)

class Quiet(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass

server = None
try:
    with patch('frappe.get_cached_doc', side_effect=cached):
        server = make_server('127.0.0.1', 0, read_only, threaded=True, request_handler=Quiet)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser_script = Path(__file__).with_name(os.environ.get('RETAIL_BROWSER_SCRIPT', Path(__file__).with_suffix('.cjs').name))
        result = subprocess.run(['node', str(browser_script)], timeout=140, env=dict(
            os.environ, RETAIL_SID=sid, RETAIL_USER=USER,
            RETAIL_URL='http://retail-test.localhost:' + str(server.server_port),
            LD_LIBRARY_PATH='/tmp/retail-accounting-browser-libs/usr/lib/x86_64-linux-gnu'))
        if result.returncode:
            raise RuntimeError('Browser verification failed')
finally:
    if server:
        server.shutdown()
    frappe.init(site=SITE, force=True)
    frappe.connect()
    frappe.cache.hdel('session', sid)
    frappe.cache.hdel('last_db_session_update', sid)
    frappe.clear_cache(user=USER)
    frappe.db.rollback()
    frappe.destroy()

"""Run Guest-entry regressions over real HTTP on the development site.

From the bench root:
  env/bin/python apps/retail/validation/guest_entry_http_tests.py

Creates a temporary user and removes it and its sessions at suite teardown.
Mail delivery and license configuration are fixtures, not persistent changes.
"""
import os, unittest, threading, http.client
from http.cookies import SimpleCookie
from urllib.parse import urlencode
from wsgiref.simple_server import make_server, WSGIRequestHandler
from pathlib import Path
os.chdir(Path(__file__).resolve().parents[3] / 'sites')
import frappe
from frappe.app import application
from werkzeug.wrappers import Response
from retail.tests.test_guest_entry import TestGuestEntry
class Quiet(WSGIRequestHandler):
    def log_message(self, *args): pass
server=make_server('127.0.0.1', 0, application, handler_class=Quiet)
threading.Thread(target=server.serve_forever, daemon=True).start()
class HTTPClient:
    def __init__(self): self.cookies={}
    def open(self, path, method='GET', base_url=None, data=None, headers=None):
        headers=dict(headers or {}); headers['Host']='retail-test.localhost'
        if self.cookies: headers['Cookie']='; '.join(k+'='+v for k,v in self.cookies.items())
        body=urlencode(data) if data else None
        if body: headers['Content-Type']='application/x-www-form-urlencoded'
        conn=http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=60)
        conn.request(method, path, body=body, headers=headers)
        response=conn.getresponse(); content=response.read()
        for key,value in response.getheaders():
            if key.lower()=='set-cookie':
                parsed=SimpleCookie(); parsed.load(value)
                for name, morsel in parsed.items(): self.cookies[name]=morsel.value
        result=Response(content, status=response.status, headers=response.getheaders()); conn.close()
        return result
TestGuestEntry.make_client=lambda self: HTTPClient()
frappe.init(site='retail-test.localhost'); frappe.connect()
try:
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(TestGuestEntry)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
finally:
    server.shutdown(); frappe.destroy()
raise SystemExit(not result.wasSuccessful())

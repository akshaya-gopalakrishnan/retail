"""Measure Guest entry over loopback HTTP on retail-test.localhost.

Usage from bench root:
  env/bin/python apps/retail/validation/guest_entry_http.py before_timing
  env/bin/python apps/retail/validation/guest_entry_http.py after_timing
  env/bin/python apps/retail/validation/guest_entry_http.py after_profile --profile

The 'before' mode disables only this change's hooks in the diagnostic process.
SQL/Redis counters and optional cProfile instrumentation are process-local.
Each route's first request uses an empty isolated Redis application namespace;
later requests use that namespace warm. The live site's cache is not flushed.
Results are written to /tmp/guest_entry_<mode>.json. Cold means application
cache, not an OS filesystem-cache purge. Timing runs must omit --profile.
"""
import os, json, time, cProfile, pstats, threading, http.client, uuid, sys
from pathlib import Path
os.chdir(Path(__file__).resolve().parents[3] / 'sites' )
import frappe
from frappe.app import application
from frappe.database.database import Database
from frappe.utils.redis_wrapper import RedisWrapper
from wsgiref.simple_server import make_server, WSGIRequestHandler
state = None
oldsql, oldredis = Database.sql, RedisWrapper.execute_command
oldmake = RedisWrapper.make_key
prefix = 'guest-entry-audit-' + uuid.uuid4().hex + '|'
def make(self, *args, **kwargs):
    key = oldmake(self, *args, **kwargs)
    return prefix.encode() + (key if isinstance(key, bytes) else str(key).encode())
RedisWrapper.make_key = make
def sql(self, *args, **kwargs):
    if state is not None: state['sql'] += 1
    return oldsql(self, *args, **kwargs)
def redis(self, *args, **kwargs):
    if state is not None: state['redis'] += 1
    return oldredis(self, *args, **kwargs)
Database.sql, RedisWrapper.execute_command = sql, redis
rows = []
prefixes = [prefix]
if sys.argv[1].startswith('before'):
    original_hooks = frappe.get_hooks
    def baseline_hooks(hook=None, *args, **kwargs):
        result = original_hooks(hook, *args, **kwargs)
        if hook == 'page_renderer': return [r for r in result if r != 'retail.guest_entry.GuestLoginPage']
        if hook == 'website_path_resolver': return []
        return result
    frappe.get_hooks = baseline_hooks
class Quiet(WSGIRequestHandler):
    def log_message(self, *args): pass
def observed(environ, start_response):
    global state
    state = {'sql': 0, 'redis': 0}
    profile = cProfile.Profile();
    if '--profile' in sys.argv: profile.enable()
    def start(status, headers, exc_info=None):
        state['status'] = status
        return start_response(status, headers, exc_info)
    try:
        result = application(environ, start)
        yield from result
        if hasattr(result, 'close'): result.close()
    finally:
        profile.disable()
        stats = pstats.Stats(profile) if '--profile' in sys.argv else None
        state['discovery'] = [{'file': f, 'name': n, 'calls': nc} for (f,l,n),(cc,nc,tt,ct,callers) in (stats.stats.items() if stats else []) if n in ('get_apps', 'get_workspace_sidebar_items', 'get_reports', 'get_allowed_reports', 'get_allowed_pages', 'get_user_pages_or_reports', 'get_permitted_report_sidebar_items', '_has_report_permission')]
        if stats is None: state['discovery'] = None
        rows.append(state); state = None
server = make_server('127.0.0.1', 0, observed, handler_class=Quiet)
thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
try:
    for index, path in enumerate(('/login','/login','/login','/app','/app','/app','/app/business-home')):
        if index == 3:
            prefix = 'guest-entry-audit-' + uuid.uuid4().hex + '|'
            prefixes.append(prefix)
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=60)
        start = time.perf_counter()
        conn.request('GET', path, headers={'Host': 'retail-test.localhost', 'Accept': 'text/html'})
        response = conn.getresponse(); ttfb = (time.perf_counter()-start)*1000
        body = response.read(); conn.close()
        deadline = time.monotonic() + 60
        while len(rows) <= index:
            if time.monotonic() > deadline: raise TimeoutError('Request profiling did not finish')
            time.sleep(.005)
        row = rows[-1]; row.update(cache='cold' if index in (0, 3) else 'warm', path=path, ttfb_ms=round(ttfb,2), location=response.getheader('Location'), body_size=len(body))
        print(json.dumps(row), flush=True)
    with open('/tmp/guest_entry_' + sys.argv[1] + '.json','w') as f: json.dump(rows,f,indent=2)
finally:
    server.shutdown()
    # Only delete this run's isolated cache; never flush the live site's Redis.
    frappe.init(site='retail-test.localhost'); cache=frappe.cache
    keys=[key for namespace in prefixes for key in cache.scan_iter(match=namespace+'*')]
    if keys: cache.delete(*keys)
    frappe.destroy()

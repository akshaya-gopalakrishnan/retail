"""Local seat authorization; no network calls or device/session limits."""
import time
import json
from html import escape

import frappe

from retail.licensing.client import DOCTYPE
from retail.licensing.state import verify_protected


def local_rules():
    settings = frappe.db.get_singles_dict(DOCTYPE)
    try:
        claims = verify_protected(
            settings.get("verified_token"), frappe.conf.get("celesta_license_public_keys", []),
            settings.get("installation_id"), time.time(),
            int(settings.get("verified_issued_at") or 0), offline=True,
        )
        rules = claims["rules"]
        return rules
    except Exception:
        frappe.throw("A valid locally verified Celesta license is required. Contact your Celesta administrator.", frappe.PermissionError)


def assigned_users():
    return frappe.get_all("Celesta Licensed User", filters={
        "parent": DOCTYPE, "parenttype": DOCTYPE, "parentfield": "licensed_users",
    }, order_by="idx asc", pluck="user")


def validate_assignments(doc):
    users = [row.user for row in doc.get("licensed_users", [])]
    if len(users) != len(set(users)):
        frappe.throw("Each licensed user may be selected only once.")
    for user in users:
        if not user or user in ("Guest", "Administrator"):
            frappe.throw("Select a user other than Guest or the emergency Administrator.")
    previous = set(assigned_users())
    # Seat removal remains possible when licensing needs repair or limits shrink.
    if set(users) - previous:
        try:
            rules = local_rules()
        except frappe.PermissionError:
            from retail.access_control import require_super_admin
            require_super_admin()
            # Recovery assignments grant no access. Signed limits apply once valid.
            frappe.clear_messages()
            rules = None
        if rules and len(users) > rules["allowed_users"]:
            frappe.throw("All licensed user seats are assigned. Remove a user before assigning another.")
        for user in set(users) - previous:
            if not frappe.db.get_value("User", user, "enabled"):
                frappe.throw("Only enabled users can be assigned a license seat.")


def check_user(user):
    # Only the built-in account has emergency recovery access.
    if user == "Administrator":
        return
    rules = local_rules()
    # Deterministic selection also enforces a centrally reduced seat allowance.
    if user not in assigned_users()[:rules["allowed_users"]]:
        frappe.throw("No Celesta license seat is assigned to your user. Contact your Celesta administrator.", frappe.PermissionError)


RECOVERY_ROUTE = "/app/celesta-license-settings"
RECOVERY_METHOD = "retail.licensing.enforcement.recovery_settings"
RECOVERY_METHODS = {
    RECOVERY_METHOD: {"GET", "POST"},
    "retail.licensing.client.activate": {"POST"},
    "retail.licensing.client.verify": {"POST"},
    "logout": {"POST"},
    "login": {"POST"},
}


def recovery_required(user):
    if user in ("Administrator", "Guest"):
        return False
    from retail.access_control import is_super_admin
    if not is_super_admin(user):
        return False
    try:
        local_rules()
    except frappe.PermissionError:
        # local_rules uses frappe.throw; do not leave a caught error in a success response.
        frappe.clear_messages()
        return True
    return False


def on_login(login_manager):
    frappe.flags.celesta_recovery_user = None
    # Frappe logs in as Guest during logout; this is not a licensed ERP login.
    if login_manager.user == "Guest":
        return
    if recovery_required(login_manager.user):
        frappe.flags.celesta_recovery_user = login_manager.user
    else:
        check_user(login_manager.user)


def on_session_creation(login_manager):
    """Remember only the restricted repair admission decided at login."""
    frappe.session.data.celesta_recovery_user = (
        login_manager.user if frappe.flags.celesta_recovery_user == login_manager.user else None
    )
    if login_manager.user != "Guest":
        frappe.local.session_obj.update(force=True)


def recovery_login():
    return (frappe.session.user not in ("Guest", "Administrator")
            and frappe.session.data.get("celesta_recovery_user") == frappe.session.user)


def recovery_request_allowed(path, method, form):
    # Reject cmd overrides even on an otherwise allowed endpoint.
    command = form.get("cmd")
    if path in ("/", "/api/method/login", "/api/method/logout") and command in ("login", "logout"):
        return path in ("/", "/api/method/" + command) and method == "POST"
    for name, methods in RECOVERY_METHODS.items():
        if path == "/api/method/" + name:
            return method in methods and command in (None, "", name)
    return False


def guard_request():
    user = frappe.session.user
    path, method = frappe.request.path, frappe.request.method
    # Logout is independent of licensing, even for restricted repair logins.
    if path == "/api/method/logout" or (path == "/" and frappe.form_dict.get("cmd") == "logout"):
        return
    if not user or not recovery_login():
        return
    if not frappe.form_dict.get("cmd") and method == "GET":
        if path == "/app":
            from werkzeug.exceptions import HTTPException
            from werkzeug.utils import redirect
            raise HTTPException(response=redirect(RECOVERY_ROUTE))
        if path == RECOVERY_ROUTE:
            from werkzeug.exceptions import HTTPException
            from werkzeug.wrappers import Response
            raise HTTPException(response=Response(recovery_page(), mimetype="text/html", headers={"Cache-Control": "no-store"}))
    if recovery_request_allowed(path, method, frappe.form_dict):
        if path == "/api/method/login" or frappe.form_dict.get("cmd") == "login":
            frappe.response["home_page"] = RECOVERY_ROUTE
            frappe.response["redirect_to"] = RECOVERY_ROUTE
        return
    frappe.throw("Licensing repair only. Open /app/celesta-license-settings or contact Administrator.", frappe.PermissionError)


@frappe.whitelist(methods=["GET", "POST"])
def recovery_settings(license_key=None, users=None):
    """Only the licensing singleton can be read or changed by this endpoint."""
    from retail.access_control import require_super_admin
    require_super_admin()
    doc = frappe.get_doc(DOCTYPE)
    if frappe.request.method == "POST":
        if license_key:
            doc.license_key = license_key
        if users is not None:
            users = frappe.parse_json(users) if isinstance(users, str) else users
            if not isinstance(users, list) or any(not isinstance(user, str) for user in users):
                frappe.throw("Licensed users must be a list of user names.")
            doc.set("licensed_users", [{"user": user} for user in users])
        doc.save()
    return {"installation_id": doc.installation_id, "status": doc.status,
            "users": [row.user for row in doc.get("licensed_users", [])]}


def recovery_page():
    from frappe.sessions import get_csrf_token
    csrf = escape(get_csrf_token(), quote=True)
    return """<!doctype html><html><head><meta charset="utf-8"><title>Celesta License Settings</title></head>
<body><h1>Celesta License Settings</h1>
<p>Administrator is the full emergency recovery account. Retail Super Admin has restricted licensing-repair access only while the license is invalid. Normal ERP access requires a valid license and an assigned seat.</p>
<p>Central URL, public pins and protected state path must be configured by the deployment operator.</p>
<p>Max Devices and Max Sessions/User: Not enforced yet.</p>
<form id="settings"><label>License Key <input id="key" type="password" autocomplete="off"></label>
<p><label>Licensed users (one exact user email per line; order determines seats)<br><textarea id="users" rows="8" cols="60"></textarea></label></p>
<p>Assignments grant no access while invalid. Put your recovery account within the signed seat allowance before activation.</p>
<button>Save</button></form><button id="activate">Activate</button><button id="verify">Sync/Verify</button>
<button id="logout">Logout</button><p><a href="/app">Log in again after recovery</a></p><pre id="result"></pre>
<script>
const csrf = """ + json.dumps(csrf) + """;
const endpoint = "/api/method/retail.licensing.enforcement.recovery_settings";
const result = document.getElementById('result');
async function call(url, data) {
 const response = await fetch(url, {method: data ? 'POST' : 'GET', headers: {'Content-Type':'application/json', 'X-Frappe-CSRF-Token':csrf}, body:data ? JSON.stringify(data):undefined});
 const body = await response.json();
 if (!response.ok) throw new Error(body._server_messages || 'Request denied or verification failed');
 return body.message;
}
async function run(fn) {try {await fn();} catch(error) {result.textContent=error.message;}}
async function load() {const data=await call(endpoint); document.getElementById('users').value=data.users.join('\\n'); result.textContent=JSON.stringify(data,null,2);}
async function save() {const users=document.getElementById('users').value.split('\\n').map(s=>s.trim()).filter(Boolean); const data=await call(endpoint,{license_key:document.getElementById('key').value,users}); document.getElementById('key').value=''; result.textContent=JSON.stringify(data,null,2);}
document.getElementById('settings').onsubmit=event=>{event.preventDefault();run(save);};
for (const action of ['activate','verify']) document.getElementById(action).onclick=()=>run(async()=>{await save(); const data=await call('/api/method/retail.licensing.client.'+action,{}); result.textContent=JSON.stringify(data)+' — If active, logout and log in again to validate your seat.';});
document.getElementById('logout').onclick=()=>run(async()=>{await call('/api/method/logout',{});location.href='/login';});
run(load);
</script></body></html>"""

"""Celesta administration boundary, using native Frappe roles and forms.

Role Profiles are editable presets, not security identities. The assigned Super
Admin role is the identity; the built-in Administrator remains the recovery user.
"""

from urllib.parse import unquote

import frappe
from frappe import _

SUPER_ADMIN = "Super Admin"
CUSTOMER_ADMIN = "Customer Administrator"
SEED_MARKER = "retail.access_control.defaults.v1"

# These configure security or executable/platform behavior, rather than business data.
PROTECTED_DOCTYPES = frozenset({
    "Repost Accounting Ledger", "Repost Accounting Ledger Settings", "Repost Allowed Types",
    "Role", "Role Profile", "Module Profile", "Module Def", "User Type",
    "User Permission", "Custom DocPerm", "DocPerm", "Has Role", "Block Module",
    "Role Permission for Page and Report", "Custom Role", "DocType", "DocField",
    "Custom Field", "Property Setter", "Customize Form", "Client Script", "Server Script",
    "System Settings", "System Console", "Console Log", "Website Settings", "Email Account", "Email Domain", "Social Login Key", "OAuth Client",
    "OAuth Provider Settings", "Connected App", "Webhook", "LDAP Settings",
    "Integration Request", "Scheduled Job Type", "Scheduled Job Log", "RQ Job",
    "Document Naming Settings", "Data Import", "Data Export", "User Invitation",
    "POS Operator Privilege", "Workflow", "Workflow State", "Workflow Action Master",
})
TECHNICAL_MODULES = frozenset({"Core", "Custom", "Integrations", "Automation", "Website", "Workflow"})
TECHNICAL_EDIT_DOCTYPES = frozenset({"Report", "Page", "Workspace", "Print Format", "Print Style", "Web Page", "Web Form", "Notification", "Email Template", "Dashboard Chart Source", "Document Naming Rule", "Custom HTML Block"})
ASSIGNMENT_FIELDS = ("role_profile_name", "module_profile", "user_type")
ASSIGNMENT_TABLES = {"roles": "role", "block_modules": "module", "user_emails": "email_account"}
PROTECTED_METHOD_PREFIXES = (
    "erpnext.accounts.doctype.repost_accounting_ledger.",
    "erpnext.accounts.doctype.repost_accounting_ledger_settings.",
    "frappe.core.page.permission_manager.", "frappe.permissions.",
    "frappe.custom.", "frappe.desk.page.setup_wizard.",
    "frappe.core.doctype.role.", "frappe.core.doctype.role_profile.",
    "frappe.core.doctype.module_profile.", "frappe.core.doctype.module_def.",
    "frappe.core.doctype.user_type.", "frappe.core.doctype.user_permission.",
    "frappe.core.doctype.user_invitation.", "frappe.core.doctype.data_import.",
    "frappe.core.doctype.data_export.", "frappe.core.doctype.doctype.",
    "frappe.core.doctype.server_script.", "frappe.core.doctype.system_settings.",
    "frappe.core.doctype.scheduled_job_type.", "frappe.core.doctype.rq_job.",
    "frappe.desk.form.customize_form.", "frappe.desk.doctype.system_console.", "frappe.desk.page.backups.",
    "frappe.desk.doctype.bulk_update.", "frappe.utils.scheduler.", "frappe.utils.backups.",
    "frappe.integrations.", "frappe.core.doctype.role_permission_for_page_and_report.",
)
PROTECTED_METHODS = frozenset({
    "frappe.core.doctype.user.user.get_role_profile",
    "frappe.core.doctype.user.user.get_module_profile",
    "frappe.core.doctype.user.user.get_all_roles",
    "frappe.core.doctype.user.user.get_perm_info",
    "frappe.core.doctype.user.user.generate_keys",
    "frappe.core.doctype.user.user.impersonate",
    "frappe.core.doctype.user.user.reset_user_data",
})
PROTECTED_PAGES = frozenset({"permission-manager", "role-permission-manager", "permission-inspector", "customize-form", "background_jobs"})


def is_super_admin(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or (user != "Guest" and SUPER_ADMIN in frappe.get_roles(user))


def deny_technical_access():
    # Do not disclose internal roles or whether a protected account exists.
    frappe.flags.retail_technical_permission_denied = True
    frappe.throw(
        _("You do not have permission to perform this action. Please contact the software team."),
        frappe.PermissionError,
        title=_("Permission Required"),
    )


def require_super_admin():
    if not is_super_admin():
        deny_technical_access()


def protected_users():
    return {"Administrator", *frappe.get_all(
        "Has Role", filters={"parenttype": "User", "role": SUPER_ADMIN}, pluck="parent"
    )}


def is_protected_user(user):
    return bool(user and (user == "Administrator" or frappe.db.exists(
        "Has Role", {"parenttype": "User", "parent": user, "role": SUPER_ADMIN}
    )))


def has_permission(doc, ptype=None, user=None, **kwargs):
    if is_super_admin(user):
        # Controller hooks may grant only permissions already present in DocPerm.
        # The seed supplies full native DocPerms for this role, at every field level.
        return True
    if doc.doctype in PROTECTED_DOCTYPES or (doc.doctype in TECHNICAL_EDIT_DOCTYPES and ptype not in ("read", "select", "print", "report", "export")):
        return False
    if doc.doctype == "User" and is_protected_user(doc.name):
        return False
    return None


def query_conditions(user=None, doctype=None):
    if is_super_admin(user):
        return ""
    if doctype in PROTECTED_DOCTYPES:
        return "1=0"
    if doctype == "User":
        return "`tabUser`.`name` != 'Administrator' AND NOT EXISTS (SELECT 1 FROM `tabHas Role` celesta_role WHERE celesta_role.parenttype = 'User' AND celesta_role.parent = `tabUser`.`name` AND celesta_role.role = 'Super Admin')"
    return ""


def _table_values(doc, field, key):
    return {row.get(key) for row in (doc.get(field) or []) if row.get(key)} if doc else set()


def validate_document(doc, method=None, *args, **kwargs):
    # Only the authenticated correction service may invoke this narrow native repost.
    if doc.doctype == "Repost Accounting Ledger" and frappe.flags.get("retail_day_correction"):
        return
    if is_super_admin():
        return
    if doc.doctype in PROTECTED_DOCTYPES or doc.doctype in TECHNICAL_EDIT_DOCTYPES:
        require_super_admin()
    previous = doc.get_doc_before_save()
    if method == "before_rename":
        if doc.doctype == "User" and is_protected_user(doc.name):
            require_super_admin()
        return
    if doc.doctype == "User":
        if is_protected_user(doc.name) or SUPER_ADMIN in _table_values(doc, "roles", "role"):
            require_super_admin()
        for field in ASSIGNMENT_FIELDS:
            old = previous.get(field) if previous else None
            new = doc.get(field)
            # Creating an unassigned standard user is allowed; custom User Types
            # can populate roles, so only standard types are accepted here.
            if not previous and field == "user_type" and new in ("System User", "Website User"):
                continue
            if field == "user_type" and method != "before_validate" and old in ("System User", "Website User") and new in ("System User", "Website User"):
                continue
            if (old or "") != (new or ""):
                require_super_admin()
        for field, key in ASSIGNMENT_TABLES.items():
            if _table_values(doc, field, key) != _table_values(previous, field, key):
                require_super_admin()
    if doc.doctype == "DocShare" and (doc.get("share_doctype") in PROTECTED_DOCTYPES or (doc.get("share_doctype") == "User" and is_protected_user(doc.get("share_name")))):
        require_super_admin()
    if doc.doctype == "Employee":
        for field in ("pos_operator_privilege", "pos_login_user", "user_id"):
            if is_protected_user(doc.get(field)) or (previous and is_protected_user(previous.get(field))):
                require_super_admin()
        if (doc.get("pos_operator_privilege") or "") != ((previous.get("pos_operator_privilege") if previous else None) or ""):
            require_super_admin()


def prepare_super_user(doc, method=None):
    """Use the native System Manager checks for tools, without changing core."""
    roles = _table_values(doc, "roles", "role")
    if SUPER_ADMIN in roles:
        if not is_super_admin():
            require_super_admin()
        doc.append_roles("System Manager")
        doc.allowed_in_mentions = 0


def guard_request():
    """Close native RPC paths that write directly, bypassing document events."""
    if is_super_admin():
        return
    form = frappe.form_dict
    path = unquote(frappe.request.path).replace("/api/v1/", "/api/", 1)
    if path.startswith("/backups"):
        require_super_admin()
    command = form.get("cmd") or (path.split("/method/", 1)[1] if "/method/" in path else "")
    if command in PROTECTED_METHODS or command.startswith(PROTECTED_METHOD_PREFIXES):
        require_super_admin()
    dt = form.get("doctype") or form.get("dt")
    name = form.get("name") or form.get("docname")
    for route in ("/api/resource/", "/api/v2/document/"):
        if route in path:
            parts = path.split(route, 1)[1].split("/")
            dt = parts[0]
            name = parts[1] if len(parts) > 1 else None
    payload = form.get("doc") or form.get("docs")
    if payload:
        try:
            payload = frappe.parse_json(payload) if isinstance(payload, str) else payload
        except (ValueError, TypeError):
            payload = None  # The native endpoint will report malformed input.
        documents = payload if isinstance(payload, list) else [payload]
        for document in documents:
            if isinstance(document, dict):
                if document.get("doctype") in PROTECTED_DOCTYPES:
                    require_super_admin()
                if document.get("doctype") == "User" and is_protected_user(document.get("name")):
                    deny_technical_access()
    if dt in PROTECTED_DOCTYPES:
        require_super_admin()
    if dt == "User" and isinstance(name, str) and is_protected_user(name):
        deny_technical_access()
    # User RPC methods may not load/check a User document at all.
    if command.startswith("frappe.core.doctype.user.user."):
        target = form.get("user") or form.get("user_name") or form.get("uid")
        if target and is_protected_user(target):
            # Public password recovery keeps the native non-enumerating response.
            if command != "frappe.core.doctype.user.user.reset_password":
                deny_technical_access()
    if command == "frappe.desk.desk_page.getpage" and form.get("name") in PROTECTED_PAGES:
        require_super_admin()


@frappe.whitelist()
def get_names_for_mentions(search_term):
    from frappe.desk.search import get_names_for_mentions as native
    rows = native(search_term)
    hidden = set() if is_super_admin() else protected_users()
    return [row for row in rows if row.get("id") not in hidden]


@frappe.whitelist(allow_guest=True, methods=["POST"])
def reset_password(user):
    from frappe.core.doctype.user.user import reset_password as native
    # Do not send recovery mail for a protected developer identity through the
    # public customer endpoint. Recovery is available to Celesta via Administrator.
    if is_protected_user(user) and not is_super_admin():
        user = "Administrator"
    return native(user)


def boot_session(bootinfo):
    bootinfo.can_manage_access = is_super_admin()


def install():
    """One-time editable defaults; never create users or replace site customizations."""
    if frappe.db.exists("Patch Log", {"patch": SEED_MARKER}):
        return
    require_super_admin()
    from retail.access_defaults import install_defaults
    install_defaults()
    frappe.get_doc({"doctype": "Patch Log", "patch": SEED_MARKER}).insert(ignore_permissions=True)
    frappe.clear_cache()

"""User-specific Retail capabilities, enforced only at external entry points.

Never use a global deny hook for linked records or server-created GL/SLE rows.
Native DocPerms still decide the operation; these rules can only deny access.
"""
import json
from urllib.parse import unquote

import frappe
from frappe.utils import cint

from retail.access_control import is_super_admin, require_super_admin
from retail.sidebar_registry import registry, entries, routes, labels, target_entries

FIELD = "retail_sidebar_permissions"
SHARED = {"Sales Invoice", "Purchase Receipt", "Stock Entry", "Customer", "Payment Entry", "Material Request"}
VAN_FLAGS = {"Sales Invoice": "custom_is_van_sale", "Stock Entry": "custom_is_van_stock_entry",
             "Customer": "custom_is_van_customer", "Payment Entry": "custom_is_van_payment",
             "Material Request": "custom_is_van_stock_request"}


def selection(user=None):
    user = user or frappe.session.user
    if user != "Administrator" and is_super_admin(user):
        return None
    value = frappe.get_cached_doc("User", user).get(FIELD)
    if not value:
        return None  # Existing users retain their current access.
    try:
        data = json.loads(value)
        return set(data["allowed"]) if data.get("version") == 1 else set()
    except (ValueError, TypeError, KeyError, AttributeError):
        return set()  # Invalid persisted configuration must fail closed.


def enabled(identifier, user=None):
    selected = selection(user)
    return selected is None or identifier in selected


def deny():
    frappe.throw(frappe._("You do not have permission to access this Retail menu."), frappe.PermissionError)


def target_allowed(kind, target, user=None):
    selected = selection(user)
    candidates = target_entries(kind, target)
    return selected is None or not candidates or any(entry["id"] in selected for entry in candidates)


def require_target(kind, target):
    if not target_allowed(kind, target):
        deny()


def document_entries(doc):
    candidates = target_entries("doctype", doc.doctype)
    flag = VAN_FLAGS.get(doc.doctype)
    is_van = flag and cint(doc.get(flag))
    for entry in candidates:
        name = entry["workspace"]
        van_menu = name.startswith("Van Sales ") or name == "Stock Request"
        if flag and bool(is_van) != van_menu:
            continue
        if doc.doctype in ("Sales Invoice", "Purchase Receipt") and not is_van:
            if bool(cint(doc.get("is_return"))) != (name in ("Sales Returns", "Purchase Returns")):
                continue
        if doc.doctype == "Stock Entry" and not is_van:
            purpose = doc.get("purpose")
            if not purpose and doc.get("stock_entry_type"):
                purpose = frappe.get_cached_value("Stock Entry Type", doc.get("stock_entry_type"), "purpose")
            manufacturing = purpose in ("Manufacture", "Material Transfer for Manufacture", "Material Consumption for Manufacture")
            if manufacturing != (name == "Stock Entries"):
                continue
        yield entry


def require_document(doc):
    selected = selection()
    if selected is not None and target_entries("doctype", doc.doctype) and not any(entry["id"] in selected for entry in document_entries(doc)):
        deny()


def validate_user(doc, method=None):
    previous = doc.get_doc_before_save()
    value = doc.get(FIELD) or ""
    old = previous.get(FIELD) or "" if previous else ""
    if value == old:
        return
    require_super_admin()
    if not value:
        return
    try:
        data = json.loads(value)
        allowed = data["allowed"]
        if data.get("version") != 1 or not isinstance(allowed, list) or not all(isinstance(key, str) for key in allowed):
            raise ValueError
        known = {entry["id"] for entry in entries()}
        if set(allowed) - known:
            raise ValueError
    except (ValueError, TypeError, KeyError):
        frappe.throw(frappe._("Invalid Retail sidebar permission selection."))
    # Parent state is derived; a parent alone cannot authorize all of its children.
    chosen = set(allowed)
    for group in registry():
        if group["children"]:
            chosen.discard(group["id"])
            if any(child["id"] in chosen for child in group["children"]):
                chosen.add(group["id"])
    doc.set(FIELD, json.dumps({"version": 1, "allowed": sorted(chosen)}, separators=(",", ":")))


def user_updated(doc, method=None):
    previous = doc.get_doc_before_save()
    if (doc.get(FIELD) or "") == ((previous.get(FIELD) if previous else None) or ""):
        return
    frappe.clear_cache(user=doc.name)
    frappe.publish_realtime("retail_sidebar_permissions_changed", user=doc.name, after_commit=True)


@frappe.whitelist()
def get_editor():
    require_super_admin()
    return registry()


def boot(bootinfo):
    bootinfo.retail_sidebar_routes = routes()
    bootinfo.retail_sidebar_labels = labels()
    bootinfo.retail_sidebar_registry = registry()
    selected = selection()
    bootinfo.retail_sidebar_selection = None if selected is None else sorted(selected)
    bootinfo.retail_sidebar_targets = {
        kind: sorted({target for entry in entries() for target_kind, target in entry["targets"]
                      if target_kind == kind and (selected is None or entry["id"] in selected)})
        for kind in ("doctype", "page", "report")
    }


def filter_sidebar(pages):
    selected = selection()
    if selected is None:
        return pages
    by_workspace = {entry["workspace"]: entry for entry in entries()}
    result = []
    for page in pages:
        name = page.get("name") or page.get("title")
        entry = by_workspace.get(name) or by_workspace.get(labels().get(name)) or by_workspace.get(page.get("title"))
        parent = by_workspace.get(page.get("parent_page"))
        if page.get("parent_page") == "Tax Reports":
            parent = by_workspace.get("Accounts Reports")
        allowed = not entry or entry["id"] in selected
        if page.get("is_report_link"):
            allowed = parent and parent["id"] in selected and target_allowed("report", page["route"][1])
        elif not entry and parent and parent["id"] in selected and name in routes():
            route = page.get("route") or routes().get(name) or routes().get(labels().get(name))
            allowed = route and (target_allowed("report", route[1]) if route[0] == "query-report" else
                                 target_allowed("doctype", route[1]) if route[0] in ("List", "Form", "Tree") else
                                 target_allowed("page", route[0]))
        # Synthetic descendants (loyalty, manufacturing and tax report groups)
        # inherit only a known selected capability, never an arbitrary new menu.
        if page.get("is_report_group") and name == "Tax Reports":
            allowed = enabled("workspace:accounts_reports")
        if allowed:
            result.append(page)
    # Empty parents disappear, even if native checks removed their last child.
    roots = {group["workspace"] for group in registry() if group["children"]}
    changed = True
    while changed:
        parents = {page.get("parent_page") for page in result}
        trimmed = [page for page in result if page.get("title") not in roots or page.get("title") in parents]
        changed = len(trimmed) != len(result)
        result = trimmed
    return result


def _json(value):
    return frappe.parse_json(value) if isinstance(value, str) else value


def filter_workspace(data, workspace):
    """Apply menu selections before Desk builds links and requests their counts."""
    selected = selection()
    if selected is None or not data:
        return data
    group = next((entry for entry in registry() if entry["workspace"] == workspace), None)

    def allowed(row, kind_field="type", target_field="link_to"):
        kind = {"DocType": "doctype", "Report": "report", "Page": "page"}.get(row.get(kind_field))
        if not kind:
            return True
        target = row.get(target_field)
        candidates = target_entries(kind, target)
        # A Sales shortcut belongs to Sales, even when Van Sales shares its DocType.
        local = [entry for entry in candidates if group and entry["parent"] == group["id"]]
        candidates = local or candidates
        # Invoices and returns share a DocType; retain the shortcut's distinction.
        label = row.get("label") or ""
        exact = [entry for entry in candidates if label in (entry["label"], entry["workspace"])]
        if not exact and kind == "doctype" and target in ("Sales Invoice", "Purchase Receipt"):
            is_return = "return" in label.lower()
            exact = [entry for entry in candidates if (entry["workspace"] in ("Sales Returns", "Purchase Returns")) == is_return]
        candidates = exact or candidates
        return not candidates or any(entry["id"] in selected for entry in candidates)

    if "shortcuts" in data:
        data["shortcuts"] = dict(data["shortcuts"], items=[
            row for row in data["shortcuts"].get("items", []) if allowed(row)])
    if "quick_lists" in data:
        data["quick_lists"] = dict(data["quick_lists"], items=[
            row for row in data["quick_lists"].get("items", [])
            if allowed(dict(row, type="DocType", link_to=row.get("document_type")))])
    if "cards" in data:
        cards = []
        for card in data["cards"].get("items", []):
            links = [row for row in card.get("links", []) if allowed(row, "link_type")]
            if links:
                cards.append(dict(card, links=links))
        data["cards"] = dict(data["cards"], items=cards)
    return data


def _target(doc):
    if not target_entries("doctype", doc.doctype):
        return
    require_target("doctype", doc.doctype)
    require_document(doc)
    # Only these explicit documents are guarded during native processing.
    frappe.flags.retail_sidebar_documents.add((doc.doctype, doc.get("name")))
    # Native form save assigns a new temporary name before validate.
    if not doc.get("name") or doc.get("__islocal") or str(doc.get("name")).startswith("new-"):
        frappe.flags.setdefault("retail_sidebar_new_doctypes", set()).add(doc.doctype)


def validate_document(doc, method=None):
    targets = frappe.flags.get("retail_sidebar_documents") or set()
    if (doc.doctype, doc.get("name")) not in targets and not (
        doc.is_new() and doc.doctype in (frappe.flags.get("retail_sidebar_new_doctypes") or set())
    ):
        return
    require_document(doc)
    previous = doc.get_doc_before_save()
    if previous:
        require_document(previous)


def has_permission(doc, ptype=None, user=None, **kwargs):
    # Read checks apply only to externally requested documents, not dependencies.
    if (doc.doctype, doc.get("name")) not in (frappe.flags.get("retail_sidebar_documents") or set()):
        return None
    selected = selection(user)
    if selected is not None and target_entries("doctype", doc.doctype) and not any(entry["id"] in selected for entry in document_entries(doc)):
        return False
    return None


def query_conditions(user=None, doctype=None):
    if (doctype != frappe.flags.get("retail_sidebar_list_doctype") and
            doctype not in (frappe.flags.get("retail_sidebar_service_doctypes") or set())) or selection(user) is None:
        return ""
    if not target_allowed("doctype", doctype, user):
        return "1=0"
    if doctype not in SHARED:
        return ""
    selected = selection(user)
    clauses = []
    for entry in target_entries("doctype", doctype):
        if entry["id"] not in selected:
            continue
        name = entry["workspace"]
        terms = []
        flag = VAN_FLAGS.get(doctype)
        van = name.startswith("Van Sales ") or name == "Stock Request"
        if flag and frappe.db.has_column(doctype, flag):
            terms.append(f"coalesce(`tab{doctype}`.`{flag}`, 0) = {int(van)}")
        if not van and doctype in ("Sales Invoice", "Purchase Receipt"):
            terms.append(f"coalesce(`tab{doctype}`.`is_return`, 0) = {int(name in ('Sales Returns', 'Purchase Returns'))}")
        if not van and doctype == "Stock Entry":
            operator = "in" if name == "Stock Entries" else "not in"
            terms.append(f"coalesce(`tabStock Entry`.`purpose`, '') {operator} ('Manufacture', 'Material Transfer for Manufacture', 'Material Consumption for Manufacture')")
        clauses.append("(" + " and ".join(terms or ["1=1"]) + ")")
    return "(" + " or ".join(clauses or ["1=0"]) + ")"


def before_job(method=None, kwargs=None, **extra):
    """Carry the external list boundary into native asynchronous exports only."""
    if method == "frappe.desk.reportview.run_report_view_export_job":
        params = (kwargs or {}).get("form_params") or {}
        frappe.flags.retail_sidebar_list_doctype = params.get("doctype")


# These endpoints expose metadata, navigation, session utilities or native link
# selection. Link selection intentionally retains native select permissions.
UTILITY_METHODS = frozenset({
    "frappe.desk.form.load.getdoctype", "frappe.desk.form.load.get_user_info_for_viewers",
    "frappe.desk.doctype.event.event.get_events",
    "frappe.desk.search.search_link", "frappe.desk.search.search_widget", "frappe.client.validate_link",
    "frappe.desk.desktop.get_workspace_sidebar_items", "frappe.apps.get_apps",
    "retail.workspace_permissions.get_workspace_sidebar_items",
    "frappe.desk.doctype.route_history.route_history.deferred_insert",
    "frappe.desk.notifications.get_notifications", "frappe.desk.notifications.mark_as_read",
    "frappe.desk.notifications.get_open_count", "frappe.desk.notifications.get_notification_settings",
    "frappe.desk.doctype.notification_log.notification_log.get_notification_logs",
    "frappe.desk.doctype.notification_log.notification_log.mark_all_as_read",
    "frappe.desk.doctype.notification_log.notification_log.mark_as_read",
    "frappe.desk.doctype.notification_settings.notification_settings.get_notification_settings",
    "frappe.desk.doctype.notification_settings.notification_settings.save_notification_settings",
    "frappe.desk.listview.get_list_settings", "frappe.desk.listview.get_listview_settings",
    "frappe.desk.listview.set_list_settings",
    "frappe.desk.search.get_names_for_mentions", "frappe.desk.search.get_recent_searches",
    "frappe.desk.search.set_recent_search",
    "frappe.desk.form.utils.getdoctype", "frappe.desk.form.utils.get_linked_doctypes",
    "frappe.model.utils.user_settings.save", "frappe.model.utils.user_settings.get",
    "frappe.client.get_time_zone", "frappe.auth.get_logged_user", "frappe.auth.logout",
    "frappe.ping", "ping", "logout", "login",
})


def guard_request():
    if selection() is None:
        return
    form = frappe.form_dict
    path = unquote(frappe.request.path).replace("/api/v1/", "/api/", 1)
    command = form.get("cmd") or (path.split("/method/", 1)[1] if "/method/" in path else "")
    frappe.flags.retail_sidebar_documents = set()
    # Keep only the built-in administrator's own configuration reachable.
    # Native User action/field permissions still apply; this grants no list access.
    if frappe.session.user == "Administrator":
        if path.rstrip("/") == "/app/user/Administrator":
            return
        if command in ("frappe.desk.form.load.getdoc", "frappe.client.get") and (
            form.get("doctype") == "User" and form.get("name") == "Administrator"
        ):
            return
        if command in ("frappe.desk.form.save.savedocs", "frappe.client.save"):
            payload = _json(form.get("doc"))
            if isinstance(payload, dict) and payload.get("doctype") == "User" and payload.get("name") == "Administrator":
                return
    if path.startswith("/private/files/"):
        links = frappe.get_all("File", filters={"file_url": path},
                               fields=["attached_to_doctype", "attached_to_name", "owner"])
        for link in links:
            dt, name = link.get("attached_to_doctype"), link.get("attached_to_name")
            if not dt and link.owner == frappe.session.user:
                return  # Native file permission checks still run afterwards.
            if dt and not target_entries("doctype", dt):
                return
            if dt and name and target_allowed("doctype", dt) and frappe.has_permission(dt, "read", doc=name):
                doc = frappe.get_doc(dt, name)
                if any(entry["id"] in selection() for entry in document_entries(doc)):
                    _target(doc)
                    return
        if links:
            deny()
        return
    if path.startswith("/app/"):
        parts = path[len("/app/"):].split("/")
        slug = parts[0]
        doctypes = {target for entry in entries() for kind, target in entry["targets"] if kind == "doctype"}
        dt = next((target for target in doctypes if frappe.scrub(target).replace("_", "-") == slug), None)
        if dt:
            require_target("doctype", dt)
            if len(parts) > 1 and frappe.db.exists(dt, parts[1]):
                _target(frappe.get_doc(dt, parts[1]))
        elif target_entries("page", slug):
            require_target("page", slug)
        elif slug == "query-report" and len(parts) > 1:
            require_target("report", parts[1])
        else:
            entry = next((entry for entry in entries() if frappe.scrub(entry["workspace"]).replace("_", "-") == slug), None)
            if entry and not enabled(entry["id"]):
                deny()
        return
    if command in UTILITY_METHODS:
        return
    if command == "frappe.desk.form.load.getdoc" and form.get("doctype") == "Report":
        # QueryReport loads its definition before running the selected report.
        require_target("report", form.get("name"))
        if any(form.get(key) for key in ("doc", "docs", "document")):
            deny()
        return  # Native getdoc still enforces Report read permissions.
    dt = form.get("doctype") or form.get("dt")
    name = form.get("name") or form.get("docname") or form.get("old_name") or form.get("dn")
    resource = False
    for prefix in ("/api/resource/", "/api/v2/document/"):
        if prefix in path:
            parts = path.split(prefix, 1)[1].strip("/").split("/")
            dt, name = parts[0], parts[1] if len(parts) > 1 else None
            resource = True
    if dt:
        # A selected transaction can still resolve linked facts without opening
        # an unchecked linked list/form. Unlisted DocTypes need no exception.
        if command == "frappe.client.get_value" and target_entries("doctype", dt) and not target_allowed("doctype", dt):
            from retail.sidebar_services import authorize_link_service
            if authorize_link_service(command, form):
                return
        require_target("doctype", dt)
    payloads = []
    for key in ("doc", "docs", "document"):
        if form.get(key):
            value = _json(form[key])
            payloads.extend(value if isinstance(value, list) else [value])
    for payload in payloads:
        if isinstance(payload, dict) and payload.get("doctype") and target_entries("doctype", payload["doctype"]):
            require_target("doctype", payload["doctype"])
            if payload.get("docname") and not payload.get("name"):
                payload = dict(payload, name=payload["docname"])
            doc = frappe.get_doc(payload)
            _target(doc)
            if doc.name and frappe.db.exists(doc.doctype, doc.name):
                _target(frappe.get_doc(doc.doctype, doc.name))
    if resource and frappe.request.method in ("POST", "PUT", "PATCH"):
        payload = dict(form)
        payload.update(doctype=dt)
        if name:
            original = frappe.get_doc(dt, name)
            _target(original)
            original.update(payload)
            _target(original)
        else:
            _target(frappe.get_doc(payload))
    if dt:
        require_target("doctype", dt)
        if isinstance(name, str) and name and frappe.db.exists(dt, name):
            _target(frappe.get_doc(dt, name))
        frappe.flags.retail_sidebar_list_doctype = dt
        if command == "frappe.client.get" and not name and form.get("filters") is not None:
            _target(frappe.get_doc(dt, _json(form.get("filters"))))
        # Validate every record before native bulk operations may enqueue a job.
        if form.get("items") and command == "frappe.desk.reportview.delete_items":
            for item in _json(form["items"]):
                _target(frappe.get_doc(dt, item))
    report = form.get("report_name") or form.get("report")
    if report:
        require_target("report", report)
    page = form.get("page_name")
    if command == "frappe.desk.desk_page.getpage":
        page = form.get("name")
        # Native Desk view shells contain framework code, not records. Their
        # subsequent document/report/workspace requests remain independently gated.
        if page in ("List", "Form", "Tree", "Workspaces", "query-report", "Report", "print"):
            return
    if page:
        require_target("page", page)
    if command in ("frappe.desk.desktop.get_desktop_page", "retail.business_home_preload.get_desktop_page"):
        page = _json(form.get("page")) or {}
        workspace = page.get("name") or page.get("title")
        entry = next((item for item in entries() if item["workspace"] == workspace), None)
        if entry and not enabled(entry["id"]):
            deny()
        return
    if resource:
        return
    if command in ("run_doc_method", "frappe.handler.run_doc_method") and (dt or payloads):
        return  # Native handler still checks the whitelisted method and actions.
    if command.startswith(("frappe.client.", "frappe.desk.form.", "frappe.desk.reportview.",
                           "frappe.desk.query_report.", "frappe.desk.desk_page.")) and (dt or report or page or payloads):
        # Native endpoints perform action permissions after this additive check.
        return
    # Controller read helpers retain native read requirements. Return factories
    # must also authorize the return capability before exposing a return draft.
    for entry in entries():
        for kind, target in entry["targets"]:
            if kind == "doctype" and f".doctype.{frappe.scrub(target)}." in command:
                require_target(kind, target)
                if not frappe.has_permission(target, "read"):
                    deny()
                function = command.rsplit(".", 1)[1]
                if function in ("make_sales_return", "make_purchase_return"):
                    require_document(frappe.get_doc({"doctype": target, "is_return": 1}))
                    if not frappe.has_permission(target, "create"):
                        deny()
                    return
                if function.startswith(("get_", "validate_")):
                    return
    # Custom services with ignore_permissions must have an explicit capability.
    from retail.sidebar_services import authorize_service
    if command.startswith("retail.") and authorize_service(command, form):
        return
    # Unlisted endpoints retain their own native/app authorization.
    return


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({"User": [
        {"fieldname": "retail_sidebar_permissions_section", "fieldtype": "Section Break",
         "label": "Retail Sidebar Permissions", "insert_after": "block_modules", "permlevel": 1,
         "depends_on": "eval:doc.user_type == 'System User'"},
        {"fieldname": "retail_sidebar_permissions_html", "fieldtype": "HTML",
         "label": "Retail Sidebar Permissions", "insert_after": "retail_sidebar_permissions_section", "permlevel": 1},
        {"fieldname": FIELD, "fieldtype": "Long Text", "hidden": 1, "permlevel": 1,
         "insert_after": "retail_sidebar_permissions_html", "no_copy": 1},
    ]}, update=True)
    frappe.clear_cache()

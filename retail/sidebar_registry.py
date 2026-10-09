"""One Retail navigation registry for the sidebar, editor and request boundary.

Workspace file identifiers and synthetic identifiers are persistence keys. Labels
may change without changing those keys. Routes are shared with the browser.
"""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent


@lru_cache(maxsize=1)
def routes():
    return json.loads((ROOT / "sidebar_routes.json").read_text())


@lru_cache(maxsize=1)
def labels():
    return json.loads((ROOT / "sidebar_labels.json").read_text())


@lru_cache(maxsize=1)
def registry():
    from retail.workspace_permissions import (
        WORKSPACE_SIDEBAR_GROUPS, SIDEBAR_DISPLAY_LABELS, REPORT_SIDEBAR_GROUPS,
    )
    documents = {}
    for path in sorted((ROOT / "retail_app/workspace").glob("*/*.json")):
        doc = json.loads(path.read_text())
        # Prefer the canonical business_home fixture over legacy home/home.json.
        documents.setdefault(doc["name"], (path.parent.name, doc))

    def entry(name, parent=None, label=None):
        filename, doc = documents.get(name, (name.lower().replace(" ", "_"), {}))
        return {"id": "workspace:" + filename, "workspace": name,
                "label": label or SIDEBAR_DISPLAY_LABELS.get(name) or doc.get("label") or name,
                "parent": parent, "route": routes().get(name), "targets": []}

    groups = []
    for root in ("Business Home", "Items", "Sales", "Purchases", "Stocks", "Accounts",
                 "Manufacturing", "POS", "Van Sales", "Reports", "Promotions", "Settings"):
        group = entry(root)
        children = [name for name, parent in WORKSPACE_SIDEBAR_GROUPS.items()
                    if parent == root and name != root and name != "Van Stock View"]
        children.sort(key=lambda name: documents.get(name, (None, {}))[1].get("sequence_id", 100))
        if root == "Purchases":
            children.remove("Material Requests")
            children.append("Material Requests")
        if root == "Van Sales":
            for name in ("Van Sales Stock View Link", "Van Sales Reports"):
                children.remove(name)
            children.insert(children.index("Van Sales Sessions Link") + 1, "Van Sales Stock View Link")
            children.append("Van Sales Reports")
        if root == "Promotions":
            children = ["Promotions " + name + " Link" for name in (
                "Promo Price", "Buy X Get Y Promotion", "Gift Voucher Promotion",
                "Gift Voucher Ledger", "Loyalty Program")]
        if root == "Reports":
            children = [name for name, _, *parent in REPORT_SIDEBAR_GROUPS if not parent]
        group["children"] = [entry(name, group["id"]) for name in children]
        for child in group["children"]:
            name = child["workspace"]
            route = child["route"]
            if route:
                kind = "doctype" if route[0] in ("List", "Form", "Tree") else "report" if route[0] == "query-report" else "page"
                child["targets"].append([kind, route[1] if kind != "page" else route[0]])
            if name == "Manufacturing Reports":
                child["label"] = "Reports"
            if name == "Manufacturing Setup":
                child["label"] = "Setup"
            if name == "Manufacturing Module Reports":
                child["label"] = "Manufacturing Module"
            report_names = []
            if name in ("Manufacturing Reports", "Manufacturing Module Reports"):
                report_names = next(reports for label, reports, *_ in REPORT_SIDEBAR_GROUPS if label == "Manufacturing Module Reports")
            elif name == "POS Reports":
                report_names = next(reports for label, reports, *_ in REPORT_SIDEBAR_GROUPS if label == "POS Sales Reports")
            elif root == "Reports":
                report_names = [report for label, reports, *parent in REPORT_SIDEBAR_GROUPS
                                if label == name or (parent and parent[0] == name) for report in reports]
            elif name == "Van Sales Reports":
                from retail.workspace_permissions import WORKSPACE_ROUTE_PERMISSIONS
                report_names = [target for rules in WORKSPACE_ROUTE_PERMISSIONS.values()
                                for kind, target in rules if kind == "report" and target.startswith("Van ")]
            child["targets"].extend(["report", report] for report in report_names)
            if name == "Manufacturing Setup":
                child["targets"].extend(["doctype", target] for target in
                    ("Operation", "Workstation", "Routing", "BOM Creator", "Manufacturing Settings"))
            if name == "Promotions Loyalty Program Link":
                child["label"] = "Loyalty Program"
                child["targets"].append(["doctype", "Loyalty Point Entry"])
            if root == "Promotions":
                child["label"] = name.removeprefix("Promotions ").removesuffix(" Link")
            if name == "Stock Request":
                child["targets"].append(["doctype", "Material Request"])
            if name == "Item Family List":
                child["targets"].append(["report", "Item Family List"])
        groups.append(group)
    # Pages can also require a document operation; reuse existing server mapping.
    from retail.workspace_permissions import WORKSPACE_ROUTE_PERMISSIONS
    for group in groups:
        for child in group["children"]:
            for target in WORKSPACE_ROUTE_PERMISSIONS.get(child["workspace"], ()):
                if list(target) not in child["targets"] and child["workspace"] != "POS Reports" and not (
                    child["workspace"] == "Item Family List" and target[0] == "doctype"
                ):
                    child["targets"].append(list(target))
    return groups


def entries():
    return [entry for group in registry() for entry in [group, *group["children"]]]


def target_entries(kind, target):
    return [entry for entry in entries() if [kind, target] in entry["targets"]]


def normalize_sidebar(pages):
    """Use the same menu order and display labels as the User editor."""
    rank = {entry["workspace"]: index for index, entry in enumerate(entries())}
    display_labels = {entry["workspace"]: entry["label"] for entry in entries()}
    result = []
    for page in pages:
        page = page.copy()
        name = page.get("name") or page.get("title")
        canonical = labels().get(name, name)
        if name in display_labels or canonical in display_labels:
            page["label"] = display_labels.get(name, display_labels.get(canonical))
        result.append(page)
    return sorted(result, key=lambda page: rank.get(page.get("name"), rank.get(labels().get(page.get("name")), rank.get(page.get("parent_page"), len(rank)))))

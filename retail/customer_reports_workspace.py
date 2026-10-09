"""Keep customer report navigation together in the report workspaces."""

import json

import frappe


CUSTOMER_REPORTS = (
    ("Customer Credit Balance", "Customer"),
    ("Customer Ledger Summary", "Sales Invoice"),
    ("Accounts Receivable", "Sales Invoice"),
    ("Accounts Receivable Summary", "Sales Invoice"),
    ("Customer-wise Item Price", "Customer"),
    ("Customer Acquisition and Loyalty", "Customer"),
    ("Inactive Customers", "Sales Order"),
    ("Customers Without Any Sales Transactions", "Sales Invoice"),
)


def add_customer_card(data):
    """Add missing customer links without replacing unrelated workspace content."""
    links = data.setdefault("links", [])
    start = next((i for i, row in enumerate(links)
                  if row.get("type") == "Card Break" and row.get("label") == "Customer"), None)
    if start is None:
        start = next((i for i, row in enumerate(links)
                      if i and row.get("type") == "Card Break"), len(links))
        links.insert(start, dict(type="Card Break", label="Customer", link_type="DocType",
                                 hidden=0, is_query_report=0, link_count=0, onboard=0))
    end = next((i for i in range(start + 1, len(links))
                if links[i].get("type") == "Card Break"), len(links))
    existing = {row.get("link_to") for row in links[start + 1:end]}
    new_links = [dict(type="Link", label=name, link_to=name, link_type="Report",
                      report_ref_doctype=doctype, is_query_report=1,
                      hidden=0, onboard=0, link_count=0)
                 for name, doctype in CUSTOMER_REPORTS if name not in existing]
    links[end:end] = new_links
    links[start]["link_count"] = end - start - 1 + len(new_links)
    content = json.loads(data.get("content") or "[]")
    if not any(row.get("type") == "card" and row.get("data", {}).get("card_name") == "Customer"
               for row in content):
        position = next((i + 1 for i, row in enumerate(content) if row.get("type") == "card"), len(content))
        content.insert(position, dict(id="card_customer", type="card", data=dict(card_name="Customer", col=4)))
    data["content"] = json.dumps(content)
    return data


def ensure_customer_report_cards():
    for name in ("Reports", "POS Reports"):
        if not frappe.db.exists("Workspace", name):
            continue
        doc = frappe.get_doc("Workspace", name)
        data = dict(content=doc.content, links=[row.as_dict() for row in doc.links])
        before = json.dumps(data, default=str)
        add_customer_card(data)
        if before != json.dumps(data, default=str):
            for idx, row in enumerate(data["links"], 1):
                row["idx"] = idx
            doc.set("links", data["links"])
            doc.content = data["content"]
            doc.save(ignore_permissions=True)
            frappe.clear_document_cache("Workspace", name)

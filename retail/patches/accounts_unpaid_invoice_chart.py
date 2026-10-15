"""Replace the two ageing widgets without changing other Accounts settings."""
import json
import frappe


def execute():
    for kind in ("dashboard_chart_source", "dashboard_chart"):
        frappe.reload_doc("retail_app", kind, "unpaid_invoice_balances")
    if not frappe.db.exists("Workspace", "Accounts"):
        return
    doc = frappe.get_doc("Workspace", "Accounts")
    old = {"Accounts Receivable Ageing", "Accounts Payable Ageing"}
    name = "Unpaid Invoice Balances"
    doc.set("charts", [r for r in doc.charts if r.chart_name not in old])
    if not any(r.chart_name == name for r in doc.charts):
        doc.append("charts", dict(chart_name=name, label=name))
    blocks = json.loads(doc.content or "[]")
    added = any(r.get("type") == "chart" and r.get("data", {}).get("chart_name") == name for r in blocks)
    content = []
    for row in blocks:
        if row.get("type") == "chart" and row.get("data", {}).get("chart_name") in old:
            if not added:
                content.append(dict(id="chart_unpaid_invoice_balances", type="chart", data=dict(chart_name=name, col=6)))
                added = True
        else:
            content.append(row)
    if not added:
        content.append(dict(id="chart_unpaid_invoice_balances", type="chart", data=dict(chart_name=name, col=6)))
    for row in content:
        if row.get("type") == "chart" and row.get("data", {}).get("chart_name") in ("Profit and Loss", name):
            row["data"]["col"] = 6
    doc.content = json.dumps(content, separators=(",", ":"))
    doc.db_update()
    doc.update_children()
    frappe.clear_cache(doctype="Workspace")

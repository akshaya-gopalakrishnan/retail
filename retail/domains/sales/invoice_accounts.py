"""Complete missing trading invoice accounts without repricing its rows."""

import frappe
from frappe import _
from frappe.utils import cint
from erpnext.stock.get_item_details import (
    get_brand_defaults,
    get_default_income_account,
    get_item_defaults,
    get_item_group_defaults,
)


def applies(doc):
    return doc.doctype == "Sales Invoice" and not any(
        cint(doc.get(field)) for field in ("is_pos", "is_consolidated", "custom_is_van_sale")
    )


def resolve_missing(doc, check_permissions=False):
    missing = [row for row in doc.get("items") or [] if row.get("item_code") and not row.get("income_account")]
    if not missing or not doc.get("company"):
        return []
    company_account = frappe.get_cached_value("Company", doc.company, "default_income_account")
    accounts = {}
    result = []
    for row in missing:
        code = row.item_code
        if code not in accounts:
            if check_permissions:
                frappe.get_cached_doc("Item", code).check_permission("read")
            # These are the same company-specific helpers used by native item loading.
            accounts[code] = get_default_income_account(
                frappe._dict(income_account=None), get_item_defaults(code, doc.company),
                get_item_group_defaults(code, doc.company), get_brand_defaults(code, doc.company),
            ) or company_account
        result.append(dict(name=row.name, item_code=code, income_account=accounts[code]))
    return result


@frappe.whitelist(methods=["POST"])
def get_missing_income_accounts(doc):
    doc = frappe.get_doc(frappe.parse_json(doc))
    if not applies(doc) or cint(doc.get("docstatus")) != 0:
        frappe.throw(_("Account defaults are available for draft trading Sales Invoices only."), frappe.ValidationError)
    doc.check_permission("create" if doc.is_new() else "write")
    if doc.get("company"):
        frappe.get_cached_doc("Company", doc.company).check_permission("read")
    return resolve_missing(doc, check_permissions=True)


def set_missing_income_accounts(doc, method=None):
    status = cint(doc.get("docstatus"))
    if not applies(doc) or (status != 0 and not (status == 1 and getattr(doc, "_action", None) == "submit")):
        return
    defaults = {entry["item_code"]: entry for entry in resolve_missing(doc)}
    for row in doc.get("items") or []:
        entry = defaults.get(row.get("item_code"))
        if entry and not row.get("income_account") and entry["income_account"]:
            row.income_account = entry["income_account"]

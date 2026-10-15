"""Lightweight, permission-filtered outstanding invoice totals for Accounts."""
import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_data(chart_name=None, chart=None, no_cache=None, filters=None, **kwargs):
    filters = frappe._dict(frappe.parse_json(filters) or {})
    company = filters.get("company") or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw(_("Please select a Company for the unpaid invoice chart."))
    frappe.get_doc("Company", company).check_permission("read")
    currency = frappe.get_cached_value("Company", company, "default_currency")
    values = []
    for doctype in ("Sales Invoice", "Purchase Invoice"):
        frappe.has_permission(doctype, "read", throw=True)
        # get_list retains native user/row permissions. Grouping avoids loading
        # invoice rows and supports invoices denominated in foreign currencies.
        rows = frappe.get_list(
            doctype,
            filters={"company": company, "docstatus": 1, "outstanding_amount": ["!=", 0]},
            fields=["party_account_currency", "conversion_rate", "sum(outstanding_amount) as outstanding"],
            group_by="party_account_currency, conversion_rate",
            order_by="", limit_page_length=0,
        )
        values.append(sum(
            flt(row.outstanding) * (1 if row.party_account_currency == currency else flt(row.conversion_rate))
            for row in rows
        ))
    return {"labels": [_("Customer Receivables"), _("Supplier Payables")],
            "datasets": [{"name": _("Unpaid Invoices ({0})").format(currency), "values": values}],
            "type": "bar"}

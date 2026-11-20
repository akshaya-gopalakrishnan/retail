"""Recover shift business dates without rewriting receipts or timestamps."""
import frappe
from frappe.utils import getdate


def execute():
    frappe.reload_doc("retail_app", "doctype", "pos_cashier_shift")
    for shift in frappe.get_all("POS Cashier Shift", fields=[
        "name", "branch", "business_date", "opening_time", "external_open_reference",
    ]):
        if shift.business_date:
            continue
        business_date = None
        if shift.external_open_reference:
            logs = frappe.get_all("POS Sync Log", filters={
                "sync_type": "Shift Opening", "external_reference": shift.external_open_reference,
                "status": ["in", ["Success", "Duplicate"]],
            }, fields=["request_json"], order_by="creation asc")
            for log in logs:
                try:
                    payload = frappe.parse_json(log.request_json or "{}")
                    payload = payload.get("payload", payload)
                    if payload.get("branch") != shift.branch:
                        continue
                    value = payload.get("business_date") or payload.get("posting_date")
                    if value:
                        business_date = getdate(value)
                        break
                except (ValueError, TypeError, AttributeError):
                    continue
        business_date = business_date or getdate(shift.opening_time)
        frappe.db.set_value("POS Cashier Shift", shift.name, "business_date", business_date, update_modified=False)

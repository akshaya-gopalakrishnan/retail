"""General Ledger display labels; retain voucher_type for Dynamic Links."""

import frappe
from frappe import _


def label_purchase_returns(output):
    rows = output["result"]
    invoices = {
        row.get("voucher_no") for row in rows
        if row.get("voucher_type") == "Purchase Invoice" and row.get("voucher_no")
    }
    returns = set(frappe.get_all(
        "Purchase Invoice", filters={"name": ["in", list(invoices)], "is_return": 1},
        pluck="name",
    )) if invoices else set()

    for column in output["columns"]:
        if column.get("fieldname") == "voucher_type":
            column["fieldname"] = "retail_voucher_type_label"
    for row in rows:
        row["retail_voucher_type_label"] = (
            _("Purchase Return")
            if row.get("voucher_type") == "Purchase Invoice" and row.get("voucher_no") in returns
            else row.get("voucher_type")
        )

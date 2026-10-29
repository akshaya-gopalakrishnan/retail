"""Project bundle identities into the standard Stock Ledger columns."""

import frappe
from frappe import _


def add_serial_numbers(columns, rows, filters=None):
    bundles = sorted({r.get("serial_and_batch_bundle") for r in rows
                      if isinstance(r, dict) and r.get("voucher_no") and r.get("serial_and_batch_bundle")})
    identities = {}
    if bundles:
        for entry in frappe.get_all("Serial and Batch Entry",
                                    filters={"parent": ["in", bundles], "parenttype": "Serial and Batch Bundle"},
                                    fields=["parent", "serial_no", "batch_no"], order_by="parent, idx"):
            values = identities.setdefault(entry.parent, {"serial_no": [], "batch_no": []})
            for field in ("serial_no", "batch_no"):
                value = entry.get(field)
                if value and value not in values[field]:
                    values[field].append(value)

    segregated = (filters or {}).get("segregate_serial_batch_bundle")
    for row in rows:
        if not isinstance(row, dict) or not row.get("voucher_no"):
            continue
        bundle = row.get("serial_and_batch_bundle")
        if bundle and not segregated:
            identity = identities.get(bundle, {})
            for field in ("serial_no", "batch_no"):
                if identity.get(field):
                    row[field] = "\n".join(identity[field])
        else:
            continue

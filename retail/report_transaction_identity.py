"""Retail-owned output adapters for standard and Retail transaction reports."""
from collections import defaultdict

import frappe
from frappe.utils import get_datetime

from retail.transaction_identity import IdentityLookup, append_columns, columns

MOVEMENT_REPORTS = {
    "Stock Movement Summary", "Damaged and Expired Stock", "Expiry Loss",
    "Supplier Wise Returns", "Supplier-wise Returns", "Cashier Wise Damage", "Margin By Movement",
    "Stock Adjustment History",
}
POS_DETAIL_REPORTS = {"POS Discount Report", "POS Price Override Report"}
POS_HEADER_REPORTS = {"POS Transaction Log", "POS Return Report"}


def reference(row):
    return (row.get("voucher_type") or row.get("document_type"),
            row.get("voucher_no") or row.get("document_no"))


def enrich_movements(rows):
    lookup = IdentityLookup({reference(row) for row in rows if isinstance(row, dict)})
    lookup.enrich(rows, reference)


def enrich_profitability_rows(rows):
    # Display enrichment belongs to report rendering, not dashboard calculations.
    targets = [r for r in rows if isinstance(r, dict) and r.get("invoice_item")
               and "retail_transaction_uom" not in r]
    enrich_movements(targets)


def ledger_key(row):
    date = row.get("date") or row.get("posting_datetime")
    from frappe.utils import flt
    return (get_datetime(date) if date else None,
            *(row.get(k) for k in ("item_code", "warehouse", "voucher_type", "voucher_no")),
            *(flt(row.get(k)) for k in ("actual_qty", "stock_value_difference", "qty_after_transaction")))


def enrich_stock_ledger(rows):
    vouchers = {r.get("voucher_no") for r in rows if isinstance(r, dict) and r.get("voucher_no")}
    if not vouchers:
        return
    entries = frappe.get_all("Stock Ledger Entry", filters={"voucher_no": ["in", sorted(vouchers)],
        "is_cancelled": 0, "docstatus": ["<", 2]},
        fields=["posting_datetime", "item_code", "warehouse", "voucher_type", "voucher_no",
                "voucher_detail_no", "actual_qty", "stock_value_difference", "qty_after_transaction", "serial_and_batch_bundle"],
        order_by="posting_datetime, creation")
    by_key = defaultdict(list)
    by_movement = defaultdict(list)
    for entry in entries:
        key = ledger_key(entry)
        by_key[key].append(entry)
        by_movement[key[:-1]].append(entry)
    by_bundle = defaultdict(list)
    for entry in entries:
        if entry.get("serial_and_batch_bundle"):
            by_bundle[(entry.voucher_type, entry.voucher_no, entry.item_code, entry.warehouse,
                       entry.serial_and_batch_bundle)].append(entry)
    targets = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("voucher_no"):
            continue
        matches = by_key.get(ledger_key(row), [])
        if matches:
            # Matching includes running balance, not just Item Code or quantity.
            row["retail_source_detail"] = matches.pop(0).voucher_detail_no
            targets.append(row)
        elif len({e.voucher_detail_no for e in by_movement.get(ledger_key(row)[:-1], [])}) == 1:
            # Batch/dimension filters can replace the displayed running balance.
            row["retail_source_detail"] = by_movement[ledger_key(row)[:-1]][0].voucher_detail_no
            targets.append(row)
        elif row.get("serial_and_batch_bundle"):
            matches = by_bundle.get((row.get("voucher_type"), row.get("voucher_no"),
                row.get("item_code"), row.get("warehouse"), row["serial_and_batch_bundle"]), [])
            details = {entry.voucher_detail_no for entry in matches}
            if len(details) == 1:
                row["retail_source_detail"] = next(iter(details))
                targets.append(row)
    # Segregated rows keep actual_qty from the parent SLE; their in/out columns
    # contain the actual displayed share. Pass that share through a temporary copy.
    pairs = [(row, dict(row, actual_qty=row["qty"]))
             if row.get("serial_and_batch_bundle") and row.get("qty") is not None
             else (row, row) for row in targets]
    enrich_movements([target for row, target in pairs])
    from retail.transaction_identity import FIELDS
    for row, target in pairs:
        if row is not target:
            row.update({key: target.get(key) for key in (*FIELDS, "retail_packing_breakdown")})


def enrich_report(report_name, result, filters=None):
    """Run before Frappe serialization/totals so exports/prepared reports agree."""
    if not result or len(result) < 2:
        return result
    output_columns, rows = result[:2]
    if not isinstance(output_columns, (list, tuple)) or not isinstance(rows, list):
        return result
    additions = []
    if report_name == "Stock Ledger":
        from retail.stock_ledger_serials import add_serial_numbers
        output_columns = list(output_columns)
        add_serial_numbers(output_columns, rows, filters)
        enrich_stock_ledger(rows)
        additions = columns(sold=False)
    elif report_name in MOVEMENT_REPORTS:
        # Movement helpers retain exact voucher_detail_no for repeated items.
        targets = [r for r in rows if isinstance(r, dict) and "retail_transaction_uom" not in r]
        if report_name == "Margin By Movement":
            from frappe.utils import flt
            from retail.transaction_identity import FIELDS
            copies = [dict(r, actual_qty=flt(r.get("qty_in")) - flt(r.get("qty_out"))) for r in targets]
            enrich_movements(copies)
            for row, enriched in zip(targets, copies):
                row.update({key: enriched.get(key) for key in (*FIELDS, "retail_packing_breakdown")})
        else:
            enrich_movements(targets)
        additions = columns(sold=False)
    elif report_name == "Van Wastage Report":
        def stock_ref(row):
            return ("Stock Entry", row.get("stock_entry"))
        IdentityLookup({stock_ref(r) for r in rows if isinstance(r, dict)}).enrich(rows, stock_ref)
        additions = columns(sold=False)
    elif report_name == "External POS Rate Audit":
        from retail.transaction_identity import resolve, parse_snapshot
        audits = frappe.get_all("External POS Rate Audit", filters={"name": ["in", [r["name"] for r in rows]]},
                               fields=["name", "pos_calculation_json"]) if rows else []
        payloads = {a.name: parse_snapshot(a.pos_calculation_json) for a in audits}
        for row in rows:
            if not row.get("item_code"):
                continue
            payload = payloads.get(row.get("name"), {})
            item = frappe.get_cached_doc("Item", row["item_code"])
            row.update(resolve(row, item, payload))
        additions = columns()
    elif report_name in ("Daily Transaction Log", "Sales Tax Report", "Purchase Tax Report", "Tax Report"):
        def invoice_ref(row):
            doctype = (row.get("doctype") if report_name == "Tax Report" else
                       "Purchase Invoice" if report_name == "Purchase Tax Report" else "Sales Invoice")
            return (doctype, row.get("invoice_no") or row.get("voucher_no"))
        IdentityLookup({invoice_ref(r) for r in rows if isinstance(r, dict)}).enrich(rows, invoice_ref)
        additions = columns(grouped=True, sold=report_name not in ("Purchase Tax Report", "Tax Report"))
    elif report_name in POS_DETAIL_REPORTS | POS_HEADER_REPORTS:
        def pos_ref(row):
            return ("POS Invoice", row.get("invoice_no") or row.get("return_invoice"))
        lookup = IdentityLookup({pos_ref(r) for r in rows if isinstance(r, dict)})
        lookup.enrich(rows, pos_ref)
        additions = columns(grouped=report_name in POS_HEADER_REPORTS)
    elif report_name in ("Sales Register", "Item-wise Sales Register"):
        def sales_ref(row):
            return ("Sales Invoice", row.get("invoice") or row.get("voucher_no"))
        lookup = IdentityLookup({sales_ref(r) for r in rows if isinstance(r, dict)})
        lookup.enrich(rows, sales_ref)
        additions = columns(grouped=report_name == "Sales Register")
    elif not any(isinstance(c, dict) and c.get("fieldname") == "retail_packing_breakdown"
                 for c in output_columns):
        if any(isinstance(r, dict) and "retail_transaction_uom" in r for r in rows):
            additions = columns()
        elif any(isinstance(r, dict) and "retail_packing_breakdown" in r for r in rows):
            additions = columns(grouped=True)
    if not additions:
        return result
    return (append_columns(output_columns, additions), rows, *result[2:])

"""Additive serial and batch fields for the existing offline POS contract."""
import frappe
from frappe.utils import cint, flt, today


def apply_master_serials(items, warehouse):
    codes = [item.item_code for item in items if cint(item.get("has_serial_no")) and not item.get("disabled")]
    by_item = {}
    if codes and warehouse:
        for serial in frappe.get_all("Serial No", filters={"item_code": ["in", codes],
                "warehouse": warehouse, "status": "Active"},
                fields=["name", "item_code"], order_by="item_code, name", limit_page_length=0):
            by_item.setdefault(serial.item_code, []).append(serial.name)
    for item in items:
        item["serial_numbers"] = by_item.get(item.item_code, [])


def apply_master_batches(items, warehouse):
    from erpnext.stock.doctype.batch.batch import get_batch_qty

    for item in items:
        item["batches"] = []
        if not cint(item.get("has_batch_no")) or item.get("disabled") or not warehouse:
            continue
        # Core combines legacy batch ledgers and bundles, subtracts reservations,
        # and excludes disabled, expired and depleted batches.
        for batch in get_batch_qty(item_code=item.item_code, warehouse=warehouse):
            if flt(batch.qty) > 0:
                item["batches"].append({"batch_no": batch.batch_no,
                    "available_qty": flt(batch.qty), "expiry_date": batch.get("expiry_date"),
                    "warehouse": warehouse})


def batch_fields(row, item):
    batch_no = row.get("batch_no")
    if batch_no is not None and not isinstance(batch_no, str):
        frappe.throw("batch_no must be a string.")
    batch_no = (batch_no or "").strip()
    if not cint(item.get("has_batch_no")):
        if batch_no:
            frappe.throw(f"Item {item.name} does not have batch tracking enabled.")
        return {}
    if not batch_no:
        return {}  # Optional: the posting flow allocates available stock.
    batch = frappe.db.get_value("Batch", batch_no, ["item", "disabled"], as_dict=True)
    if not batch or batch.item != item.name or cint(batch.disabled):
        frappe.throw(f"Batch {batch_no} is not an enabled batch for Item {item.name}.")
    return {"batch_no": batch_no, "use_serial_batch_fields": 1}


def serial_fields(row, item, seen=None):
    selected_batch = batch_fields(row, item)
    raw = row.get("serial_no")
    if raw is not None and not isinstance(raw, str):
        frappe.throw("serial_no must be a newline-separated string.")
    serials = [value.strip() for value in (raw or "").splitlines() if value.strip()]
    if not cint(item.get("has_serial_no")):
        if serials:
            frappe.throw(f"Item {item.name} does not have serial tracking enabled.")
        return selected_batch
    if not serials:
        # A batch alone must not enable legacy fields on a serialized item:
        # let the posting flow allocate serials within that batch instead.
        return {"batch_no": selected_batch["batch_no"]} if selected_batch else {}
    factor = flt(row.get("conversion_factor"))
    if not factor:
        uom = row.get("uom") or item.stock_uom
        factor = 1 if uom == item.stock_uom else next(
            (flt(d.conversion_factor) for d in item.get("uoms", []) if d.uom == uom), 0)
    qty = abs(flt(row.get("qty")) * factor)
    if not serials or not factor or qty != len(serials):
        frappe.throw(f"Item {item.name} requires one serial_no per stock unit (stock quantity: {qty}).")
    if len(set(serials)) != len(serials) or (seen is not None and seen.intersection(serials)):
        frappe.throw(f"Duplicate serial_no in POS items for {item.name}.")
    if seen is not None:
        seen.update(serials)
    fields = {"serial_no": "\n".join(serials), "use_serial_batch_fields": 1}
    if cint(item.get("has_batch_no")):
        batches = set(frappe.get_all("Serial No", filters={"name": ["in", serials],
            "item_code": item.name}, pluck="batch_no"))
        if len(batches) != 1 or not next(iter(batches), None):
            frappe.throw(f"Item {item.name}: select serials from one batch per item row.")
        fields["batch_no"] = next(iter(batches))
        if selected_batch and selected_batch["batch_no"] != fields["batch_no"]:
            frappe.throw(f"Item {item.name}: batch_no does not match the selected serials.")
    return fields


def allocate_missing_tracking(doc):
    """Allocate omitted POS tracking server-side; retain explicit selections."""
    from collections import defaultdict
    from erpnext.stock.doctype.batch.batch import get_available_batches
    from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos_for_outward
    from erpnext.stock.serial_batch_bundle import SerialBatchCreation
    from erpnext.stock.stock_ledger import is_negative_stock_allowed

    if doc.is_return:
        # Native return allocation uses the original document's still-returnable
        # bundles, never today's unrelated warehouse stock.
        doc.make_bundle_for_sales_purchase_return()
        return

    used_batches = defaultdict(float)
    used_serials = set()
    based_on = frappe.db.get_single_value("Stock Settings", "pick_serial_and_batch_based_on") or "FIFO"
    for row in doc.items:
        if row.get("use_serial_batch_fields"):
            used_serials.update((row.get("serial_no") or "").splitlines())
        if row.get("batch_no") and row.get("use_serial_batch_fields"):
            used_batches[(row.item_code, row.warehouse, row.batch_no)] += abs(flt(row.stock_qty))
        if row.get("serial_and_batch_bundle"):
            for entry in frappe.get_all("Serial and Batch Entry", filters={"parent":row.serial_and_batch_bundle},
                                        fields=["serial_no", "batch_no", "qty"]):
                if entry.serial_no:
                    used_serials.add(entry.serial_no)
                if entry.batch_no:
                    used_batches[(row.item_code,row.warehouse,entry.batch_no)] += abs(flt(entry.qty))

    for row in doc.items:
        if row.get("serial_and_batch_bundle") or row.get("use_serial_batch_fields"):
            continue
        item = frappe.get_cached_doc("Item", row.item_code)
        if not (item.has_serial_no or item.has_batch_no):
            continue
        qty = abs(flt(row.stock_qty))
        kwargs = frappe._dict(item_code=row.item_code, warehouse=row.warehouse,
            qty=qty, based_on=based_on, posting_date=doc.posting_date, posting_time=doc.posting_time,
            ignore_serial_nos=list(used_serials))
        args = dict(item_code=row.item_code, warehouse=row.warehouse, qty=qty,
            voucher_type=doc.doctype, voucher_no=None if doc.is_new() else doc.name, voucher_detail_no=row.name,
            posting_date=doc.posting_date, posting_time=doc.posting_time, company=doc.company,
            type_of_transaction="Outward", do_not_submit=True)
        if item.has_serial_no:
            if row.get("batch_no"):
                kwargs.batches = row.batch_no
            args["serial_nos"] = get_serial_nos_for_outward(kwargs)
            if len(args["serial_nos"]) != qty:
                frappe.throw(f"Insufficient available serial stock for Item {row.item_code}.")
            used_serials.update(args["serial_nos"])
        else:
            # Fetch batches in the configured order, deducting earlier rows.
            allow_negative = cint(frappe.db.get_single_value(
                "Stock Settings", "allow_negative_stock_for_batch"
            )) and is_negative_stock_allowed(item_code=row.item_code)
            kwargs.qty = 0
            kwargs.consider_negative_batches = bool(allow_negative)
            available_batches = get_available_batches(kwargs)
            remaining = qty
            selected = {}
            for batch, available in available_batches.items():
                key = (row.item_code, row.warehouse, batch)
                take = min(remaining, max(0, flt(available) - used_batches[key]))
                if take:
                    selected[batch] = take
                    used_batches[key] += take
                    remaining -= take
                if remaining <= 0:
                    break
            if remaining > 0:
                if not allow_negative:
                    frappe.throw(f"Insufficient available batch stock for Item {row.item_code}.")
                if not available_batches:
                    # A backdated sale may precede the batch's first receipt.
                    # Negative stock needs a valid identity, not prior stock.
                    batch_order = "creation desc, name desc" if based_on == "LIFO" else "creation asc, name asc"
                    batches = frappe.get_all("Batch",
                        filters={"item": row.item_code, "disabled": 0},
                        or_filters=[["expiry_date", ">=", today()],
                                    ["expiry_date", "is", "not set"]],
                        fields=["name", "expiry_date"], order_by=batch_order, limit_page_length=0)
                    if based_on == "Expiry":
                        batches.sort(key=lambda batch: str(batch.expiry_date or "9999-12-31"))
                    if not batches:
                        frappe.throw(
                            f"No enabled, unexpired batch exists for Item {row.item_code}. "
                            "Create a valid batch to allow negative batch stock."
                        )
                    available_batches = {batches[0].name: 0}
                # Assign the shortage using the configured selection order.
                batch = next(iter(available_batches))
                selected[batch] = selected.get(batch, 0) + remaining
                used_batches[(row.item_code, row.warehouse, batch)] += remaining
            args["batches"] = selected
        row.serial_and_batch_bundle = SerialBatchCreation(args).make_serial_and_batch_bundle().name
        # Item-detail defaults may fill legacy fields before this validation.
        # The bundle now owns the allocation, including splits across batches.
        row.serial_no = ""
        row.batch_no = ""

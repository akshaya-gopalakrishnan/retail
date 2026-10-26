"""Additive transaction display facts; never alter quantities or accounting fields."""
from collections import defaultdict
import json

import frappe
from frappe import _
from frappe.utils import flt

SNAPSHOT = "custom_retail_transaction_identity"
CHILDREN = {
    "Sales Invoice": "Sales Invoice Item", "POS Invoice": "POS Invoice Item",
    "Delivery Note": "Delivery Note Item", "Purchase Invoice": "Purchase Invoice Item",
    "Purchase Receipt": "Purchase Receipt Item", "Stock Entry": "Stock Entry Detail",
}
FIELDS = ("retail_transaction_uom", "retail_transaction_barcode", "retail_transaction_name",
          "retail_transaction_qty", "retail_transaction_factor", "retail_identity_source")


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({child: [dict(fieldname=SNAPSHOT, label="Retail Transaction Identity",
        fieldtype="Code", options="JSON", hidden=1, read_only=1, no_copy=1)]
        for child in CHILDREN.values()}, update=True)


def parse_snapshot(value):
    if not value:
        return {}
    try:
        result = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return {}
    return result if isinstance(result, dict) else {}


def payload_items(value):
    items = parse_snapshot(value).get("items")
    return [row if isinstance(row, dict) else {} for row in items] if isinstance(items, list) else []


def resolve(line, item, payload=None, *, use_snapshot=True):
    """Use persisted facts; current-master inference is explicitly labelled."""
    saved = parse_snapshot(line.get(SNAPSHOT)) if use_snapshot else {}
    if saved.get("version") == 1:
        return {key: saved.get(key) for key in FIELDS}
    payload = payload or {}
    uom = line.get("uom") or payload.get("uom")
    factor = line.get("conversion_factor")
    if factor is None:
        factor = payload.get("conversion_factor")
    barcode = str(line.get("barcode") or payload.get("barcode") or "").strip()
    name = line.get("item_name") or payload.get("item_name") or item.get("item_name")
    source = "Recorded transaction"
    packs = item.get("custom_retail_packing_detail") or []
    if barcode:
        matches = [p for p in packs if str(p.get("barcode") or "").strip() == barcode
                   and (not uom or p.get("uom") == uom)
                   and (factor is None or flt(p.get("conversion_factor")) == flt(factor))]
    else:
        matches = [p for p in packs if uom and p.get("uom") == uom and factor is not None
                   and flt(p.get("conversion_factor")) == flt(factor)
                   and (uom != item.get("stock_uom") or flt(factor) != 1)]
    if len(matches) == 1 and matches[0].get("packing_name"):
        name = matches[0].get("packing_name")
        source += "; packing name from current Item setup"
    elif (uom and uom != item.get("stock_uom")) or (factor is not None and flt(factor) != 1):
        # Retain the saved line name but make unavailable packing identity explicit.
        source += "; packing name not verified" if barcode else "; barcode not recorded"
    if not barcode and "barcode not recorded" not in source:
        source += "; barcode not recorded"
    return dict(zip(FIELDS, (uom, barcode or _("Not recorded"), name,
        line.get("qty") if line.get("qty") is not None else payload.get("qty"),
        factor, source)))


def source_quantity(values, line):
    """Consolidation/returns retain the source packing but use this line's stock quantity."""
    values = dict(values)
    factor = flt(values.get("retail_transaction_factor"))
    if line.get("stock_qty") is not None and factor:
        values["retail_transaction_qty"] = flt(line.get("stock_qty")) / factor
    elif line.get("uom") == values.get("retail_transaction_uom"):
        values["retail_transaction_qty"] = line.get("qty")
    else:
        values["retail_transaction_qty"] = None
    return values


def snapshot_document(doc, method=None):
    """Only new submissions: no historical repair and no guessed scanned barcode."""
    payload_rows = payload_items(doc.get("custom_pos_completed_payload"))
    for index, line in enumerate(doc.get("items") or []):
        if not line.meta.has_field(SNAPSHOT):
            continue
        item = (frappe.get_cached_doc("Item", line.item_code) if line.get("item_code") else
                frappe._dict(item_name=line.get("item_name"), stock_uom=line.get("stock_uom")))
        original = payload_rows[index] if index < len(payload_rows) else {}
        # Payload position is accepted only when its item code agrees.
        if original.get("item_code") and original["item_code"] != line.item_code:
            original = {}
        values = resolve(line, item, original, use_snapshot=False)
        if doc.get("doctype") == "Sales Invoice" and line.get("pos_invoice") and line.get("pos_invoice_item"):
            source_doc = frappe.get_cached_doc("POS Invoice", line.pos_invoice)
            source_line = next((p for p in source_doc.items if p.name == line.pos_invoice_item
                                and p.item_code == line.item_code), None)
            if source_line:
                source_payload = payload_items(source_doc.get("custom_pos_completed_payload"))
                source_index = int(source_line.idx) - 1
                source_row = source_payload[source_index] if 0 <= source_index < len(source_payload) else {}
                values = source_quantity(resolve(source_line, item, source_row), line)
        values["retail_identity_source"] = "Saved at submission; " + values["retail_identity_source"]
        line.set(SNAPSHOT, json.dumps(dict(version=1, **values), ensure_ascii=False))


class IdentityLookup:
    """One request-local cache; batch read only source documents already in report."""
    def __init__(self, references):
        self.lines = {}
        self.items = {}
        self.payloads = {}
        by_type = defaultdict(set)
        for doctype, name in references:
            if doctype in CHILDREN and name:
                by_type[doctype].add(name)
        item_codes = set()
        for doctype, names in by_type.items():
            child = CHILDREN[doctype]
            meta = frappe.get_meta(child)
            wanted = ["name", "parent", "idx", "item_code", "item_name", "uom", "stock_uom",
                      "qty", "stock_qty", "conversion_factor", "barcode", "warehouse",
                      "pos_invoice", "pos_invoice_item", SNAPSHOT]
            fields = [f for f in wanted if f in ("name", "parent", "idx") or meta.has_field(f)]
            for line in frappe.get_all(child, filters={"parent": ["in", sorted(names)],
                    "parenttype": doctype}, fields=fields, order_by="parent, idx"):
                self.lines.setdefault((doctype, line.parent), []).append(line)
                if line.get("item_code"):
                    item_codes.add(line.item_code)
            if frappe.get_meta(doctype).has_field("custom_pos_completed_payload"):
                for parent in frappe.get_all(doctype, filters={"name": ["in", sorted(names)]},
                        fields=["name", "custom_pos_completed_payload"]):
                    self.payloads[(doctype, parent.name)] = payload_items(parent.custom_pos_completed_payload)
        if item_codes:
            for item in frappe.get_all("Item", filters={"name": ["in", sorted(item_codes)]},
                    fields=["name", "item_name", "stock_uom"]):
                item["custom_retail_packing_detail"] = []
                self.items[item.name] = item
            for packing in frappe.get_all("Retail Packing Detail", filters={"parent": ["in", sorted(item_codes)],
                    "parenttype": "Item", "parentfield": "custom_retail_packing_detail"},
                    fields=["parent", "barcode", "packing_name", "uom", "conversion_factor"]):
                if packing.parent in self.items:
                    self.items[packing.parent]["custom_retail_packing_detail"].append(packing)

        originals = {("POS Invoice", line.get("pos_invoice"))
                     for (doctype, name), lines in self.lines.items() if doctype == "Sales Invoice"
                     for line in lines if line.get("pos_invoice") and line.get("pos_invoice_item")}
        self.pos_lookup = IdentityLookup(originals) if originals else None

    def values(self, reference, line):
        if reference[0] == "Sales Invoice" and line.get("pos_invoice_item"):
            source_ref = ("POS Invoice", line.get("pos_invoice"))
            source_line = next((p for p in self.pos_lookup.lines.get(source_ref, [])
                                if p.name == line.pos_invoice_item and p.item_code == line.item_code), None) if self.pos_lookup else None
            if source_line and not parse_snapshot(line.get(SNAPSHOT)).get("version"):
                return source_quantity(self.pos_lookup.values(source_ref, source_line), line)
        payloads = self.payloads.get(reference, [])
        index = int(line.get("idx") or 0) - 1
        payload = payloads[index] if 0 <= index < len(payloads) else {}
        if payload.get("item_code") and payload["item_code"] != line.item_code:
            payload = {}
        return resolve(line, self.items.get(line.item_code, {}), payload)

    def enrich(self, rows, reference):
        for row in rows:
            if not isinstance(row, dict) or row.get("is_total_row"):
                continue
            ref = reference(row)
            lines = self.lines.get(ref, [])
            detail = row.get("voucher_detail_no") or row.get("invoice_item") or row.get("retail_source_detail")
            if detail:
                lines = [line for line in lines if line.name == detail]
            elif row.get("item_index"):
                lines = [line for line in lines if line.idx == row["item_index"]]
            elif row.get("item_code"):
                lines = [line for line in lines if line.item_code == row["item_code"]
                         and (not row.get("warehouse") or not line.get("warehouse")
                              or line.warehouse == row["warehouse"])]
            if row.get("item_code"):
                lines = [line for line in lines if line.item_code == row["item_code"]]
            if not lines:
                continue
            identities = [self.values(ref, line) for line in lines]
            if len(identities) == 1:
                row.update(identities[0])
                # SLE rows may split one document line by batch/serial/warehouse.
                # Display only the movement's share, never repeat the full invoice quantity.
                movement_qty = row.get("actual_qty")
                if movement_qty is None and ref[0] == "Stock Entry":
                    movement_qty = row.get("net_qty")
                if movement_qty is not None:
                    factor = identities[0].get("retail_transaction_factor")
                    row["retail_transaction_qty"] = (flt(movement_qty) / flt(factor)
                        * (-1 if ref[0] in ("Sales Invoice", "POS Invoice", "Delivery Note") else 1)
                        if flt(factor) else None)
            else:
                for key in FIELDS:
                    values = {v.get(key) for v in identities}
                    row[key] = next(iter(values)) if len(values) == 1 and key != "retail_transaction_qty" else None
                if (len({(v.get(FIELDS[0]), v.get(FIELDS[4])) for v in identities}) == 1
                        and all(v.get("retail_transaction_qty") is not None for v in identities)):
                    row["retail_transaction_qty"] = sum(flt(v.get("retail_transaction_qty")) for v in identities)
                row["retail_identity_source"] = "Multiple source lines; see packing breakdown"
            if len(identities) == 1:
                identities = [{**identities[0], "retail_transaction_qty": row.get("retail_transaction_qty")}]
            row["retail_packing_breakdown"] = packing_breakdown(identities)


def packing_breakdown(identities):
    groups = {}
    for value in identities:
        key = tuple(value.get(k) for k in (FIELDS[2], FIELDS[0], FIELDS[1], FIELDS[4]))
        qty = value.get(FIELDS[3])
        previous = groups.get(key, 0)
        groups[key] = None if qty is None or previous is None else previous + flt(qty)
    parts = []
    for (name, uom, barcode, factor), qty in sorted(groups.items(), key=lambda pair: str(pair[0])):
        quantity = "?" if qty is None else f"{qty:g}"
        parts.append(f"{quantity} {uom or '?'} | {barcode or _('Not recorded')} | {name or '?'}"
                     + (f" | x{flt(factor):g}" if factor is not None else ""))
    return "; ".join(parts)


def columns(*, sold=True, grouped=False):
    if grouped:
        return []
    # Data columns deliberately avoid summing quantities in mixed UOMs or conversion factors.
    prefix = "Sold" if sold else "Transaction"
    return [dict(fieldname=field, label=_(label), fieldtype=kind, width=width, **extra)
            for field, label, kind, width, extra in [
                (FIELDS[0], f"{prefix} UOM", "Link", 110, {"options": "UOM"}),
                (FIELDS[1], f"{prefix} Barcode", "Data", 150, {}),
                (FIELDS[2], f"{prefix} Item / Packing Name", "Data", 230, {}),
                (FIELDS[3], f"{prefix} Qty", "Data", 110, {}),
                (FIELDS[4], "UOM Conversion Factor", "Data", 130, {}),
            ]]


def append_columns(existing, additions):
    names = {c.get("fieldname") for c in existing if isinstance(c, dict)}
    return [*existing, *(c for c in additions if c["fieldname"] not in names)]

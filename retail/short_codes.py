"""Compact document identifiers with permanent, locked sequence counters."""
import json
import os
import re
from unittest.mock import patch

import frappe
from frappe.model.naming import getseries

PREFIXES = {
    "Customer": "C", "Supplier": "S", "Employee": "E", "Item": "I", "Driver": "DR",
    "Quotation": "QT", "Sales Order": "SO", "Sales Invoice": "SI",
    "POS Invoice": "POS", "Delivery Note": "DN", "Purchase Order": "PO",
    "Purchase Receipt": "PR", "Purchase Invoice": "PI", "Supplier Quotation": "SQ",
    "Request for Quotation": "RFQ", "Payment Entry": "PE", "Journal Entry": "JE",
    "Material Request": "MR", "Stock Entry": "SE", "Stock Reconciliation": "SR",
    "Landed Cost Voucher": "LCV", "Payment Request": "PAYR",
    "POS Opening Entry": "POE", "POS Closing Entry": "PCE",
    "POS Invoice Merge Log": "PIM", "POS Counter Session": "PCS",
    "POS Cashier Shift": "PSH", "POS Cash Movement": "PCM",
    "POS Branch Day Closing": "PDC", "POS Sync Log": "PSL",
    "Van Session": "VSS", "Van Loading Entry": "VL", "Cashier Closing": "CC",
    "Retail Item Rate Audit": "RA",
}


def prefix_for(doc):
    if doc.doctype == "Sales Invoice":
        if doc.get("is_consolidated"):
            return "PSI"
        if doc.get("custom_is_van_sale"):
            return "VS"
    return PREFIXES.get(doc.doctype)


def next_code(prefix):
    # Dedicated counter keys are not decremented by Frappe's delete-document logic.
    # All document types sharing a prefix also share the same locked counter.
    while True:
        name = prefix + "-" + getseries("retail-short-code:" + prefix, 1)
        if not any(frappe.db.exists(dt, name) for dt in PREFIXES if frappe.db.exists("DocType", dt)):
            return name


def autoname(doc, method=None):
    prefix = prefix_for(doc)
    if prefix:
        try:
            doc.name = next_code(prefix)
            if doc.doctype == "Item":
                doc.item_code = doc.name
            elif doc.doctype == "Employee":
                doc.employee = doc.name
        finally:
            if doc.flags.short_code_amended_from:
                doc.amended_from = doc.flags.short_code_amended_from
                doc.flags.short_code_amended_from = None


def before_naming(doc, method=None):
    prefix = prefix_for(doc)
    if prefix:
        # Frappe otherwise returns early with a reusable amendment suffix.
        # Restore the amendment link in autoname before validation or insertion.
        if doc.get("amended_from"):
            doc.flags.short_code_amended_from = doc.amended_from
            doc.amended_from = None
        if doc.meta.has_field("naming_series"):
            doc.naming_series = prefix + "-.#"


def install(doctypes=None):
    from retail.naming import _set_doctype_property
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    for dt in (doctypes or PREFIXES):
        prefix = PREFIXES[dt]
        if not frappe.db.exists("DocType", dt):
            continue
        if dt == "Employee":
            frappe.db.set_single_value("HR Settings", "emp_created_by", "Naming Series")
        if dt in ("Customer", "Supplier"):
            settings, field = ("Selling Settings", "cust_master_name") if dt == "Customer" else ("Buying Settings", "supp_master_name")
            frappe.db.set_single_value(settings, field, "Naming Series")
            frappe.defaults.set_global_default(field, "Naming Series")
        meta = frappe.get_meta(dt)
        if meta.has_field("naming_series"):
            choices = [prefix + "-.#"]
            if dt == "Sales Invoice":
                choices += ["VS-.#", "PSI-.#"]
            for prop, value, kind in (("options", "\n".join(choices), "Text"), ("default", choices[0], "Data")):
                make_property_setter(dt, "naming_series", prop, value, kind, validate_fields_for_doctype=False)
        _set_doctype_property(dt, "autoname", "naming_series:" if meta.has_field("naming_series") else prefix + "-.#", "Data")
        for rule in frappe.get_all("Document Naming Rule", filters={"document_type": dt, "disabled": 0}, pluck="name"):
            frappe.db.set_value("Document Naming Rule", rule, "disabled", 1)
        # Pre-create keys so concurrent first inserts lock an existing row.
        for code in ([prefix, "PSI", "VS"] if dt == "Sales Invoice" else [prefix]):
            frappe.db.sql("INSERT IGNORE INTO `tabSeries` (`name`, `current`) VALUES (%s, 0)", ("retail-short-code:" + code,))
    frappe.clear_cache()


def inventory():
    return {dt: frappe.db.count(dt) for dt in PREFIXES if frappe.db.exists("DocType", dt)}


def migrate_existing(doctypes=None):
    """Explicit site operation; preserve typed links using Frappe's rename engine."""
    from frappe.model.rename_doc import rename_doc
    install(doctypes)
    mapping = []
    path = frappe.get_site_path("private", "files", "short-code-renames.json")
    if os.path.exists(path):
        with open(path) as stream:
            mapping = json.load(stream)
    for dt in (doctypes or PREFIXES):
        if not frappe.db.exists("DocType", dt):
            continue
        for name in frappe.get_all(dt, pluck="name", order_by="creation asc, name asc"):
            doc = frappe.get_doc(dt, name)
            prefix = prefix_for(doc)
            if re.fullmatch(re.escape(prefix) + r"-[1-9][0-9]*(?:-[1-9][0-9]*)?", name):
                continue
            display_field = {"Item": "item_name", "Employee": "employee_name", "Driver": "full_name"}.get(dt)
            display_name = doc.get(display_field) if display_field else None
            new = next_code(prefix)
            # Schema is fixed during this explicit bulk operation. Defer global
            # metadata invalidation; rename_doc still clears each document cache.
            with patch("frappe.clear_cache"):
                rename_doc(dt, name, new, force=True, ignore_permissions=True, show_alert=False, rebuild_search=False)
            if display_field:
                frappe.db.set_value(dt, new, display_field, display_name, update_modified=False)
            if doc.meta.has_field("naming_series"):
                frappe.db.set_value(dt, new, "naming_series", prefix + "-.#", update_modified=False)
            mapping.append({"doctype": dt, "old": name, "new": new})
        # Commit each document type and retain a mapping for bookmarks/auditing.
        with open(path, "w") as stream:
            json.dump(mapping, stream, indent=2)
        frappe.db.commit()
        print(f"{dt}: renamed; total {len(mapping)}", flush=True)
    repair_sync_references()
    frappe.clear_cache()
    return {"renamed": len(mapping), "mapping": path}


def verify():
    """Exercise the actual naming hooks without keeping test records/counters."""
    from frappe.model.naming import set_new_name, revert_series_if_last
    names = []
    frappe.db.savepoint("short_code_verification")
    try:
        for dt, values, expected in (
            ("Purchase Order", {}, "PO"),
            ("Sales Invoice", {}, "SI"),
            ("Sales Invoice", {"is_pos": 1}, "SI"),
            ("Sales Invoice", {"custom_is_van_sale": 1}, "VS"),
            ("POS Invoice", {}, "POS"),
            ("Sales Invoice", {"is_consolidated": 1, "is_pos": 1}, "PSI"),
            ("Sales Invoice", {"is_consolidated": 1, "is_return": 1}, "PSI"),
            ("Van Session", {}, "VSS"),
            ("Employee", {"first_name": "Code Test"}, "E"),
            ("Item", {"item_name": "Code Test"}, "I"),
            ("Driver", {"full_name": "Code Test"}, "DR"),
            ("Purchase Order", {"amended_from": "PO-1"}, "PO"),
        ):
            doc = frappe.new_doc(dt)
            doc.update(values)
            set_new_name(doc)
            assert re.fullmatch(expected + r"-[1-9][0-9]*", doc.name), doc.name
            if values.get("amended_from"):
                assert doc.amended_from == values["amended_from"]
            assert doc.name not in names
            names.append(doc.name)
            if doc.get("naming_series"):
                revert_series_if_last(doc.naming_series, doc.name, doc)
                following = next_code(expected)
                assert int(following.split("-")[1]) > int(doc.name.split("-")[1])
        log = frappe.get_doc({"doctype": "POS Sync Log", "sync_type": "Item Pull", "status": "Pending"})
        log.insert(ignore_permissions=True)
        deleted_code = log.name
        frappe.delete_doc("POS Sync Log", deleted_code, ignore_permissions=True, force=True)
        replacement = frappe.get_doc({"doctype": "POS Sync Log", "sync_type": "Item Pull", "status": "Pending"})
        replacement.insert(ignore_permissions=True)
        assert int(replacement.name.split("-")[1]) > int(deleted_code.split("-")[1])
        duplicate = frappe.copy_doc(replacement)
        duplicate.name = replacement.name
        duplicate.docstatus = 0
        try:
            duplicate.db_insert()
        except frappe.DuplicateEntryError:
            pass
        else:
            raise AssertionError("Database accepted a duplicate document code")
        return {"passed": True, "sample_codes": names, "deletion_does_not_reuse": True, "duplicate_rejected": True}
    finally:
        frappe.db.rollback(save_point="short_code_verification")


def repair_sync_references():
    """Update cached POS responses; keep original request payloads as audit evidence."""
    with open(frappe.get_site_path("private", "files", "short-code-renames.json")) as stream:
        rows = json.load(stream)
    mapping = {}
    party_mapping = {}
    ambiguous = set()
    for row in rows:
        if row["doctype"] in ("Customer", "Supplier", "Item", "Employee", "Driver"):
            party_mapping[(row["doctype"], row["old"])] = row["new"]
            continue
        if row["old"] in mapping and mapping[row["old"]] != row["new"]:
            ambiguous.add(row["old"])
        mapping[row["old"]] = row["new"]
    for old in ambiguous:
        mapping.pop(old)

    def replace(value):
        if isinstance(value, dict):
            updated = {key: replace(item) for key, item in value.items()}
            for key, dt in (("customer", "Customer"), ("customer_id", "Customer"), ("supplier", "Supplier"), ("supplier_id", "Supplier"), ("item_code", "Item"), ("item", "Item"), ("employee", "Employee"), ("employee_id", "Employee"), ("cashier_employee", "Employee"), ("driver", "Driver")):
                if isinstance(value.get(key), str):
                    updated[key] = party_mapping.get((dt, value[key]), updated[key])
            dt = value.get("doctype")
            if not dt:
                dt = "Customer" if "customer_name" in value else "Supplier" if "supplier_name" in value else "Item" if "item_name" in value else "Employee" if "employee_name" in value else None
            if isinstance(value.get("name"), str) and dt in ("Customer", "Supplier", "Item", "Employee", "Driver"):
                updated["name"] = party_mapping.get((dt, value["name"]), updated["name"])
            return updated
        if isinstance(value, list):
            return [replace(item) for item in value]
        return mapping.get(value, value) if isinstance(value, str) else value

    changed = 0
    for log in frappe.get_all("POS Sync Log", fields=["name", "sync_type", "erpnext_docname", "response_json"]):
        values = {}
        if log.sync_type == "Customer Upsert" and ("Customer", log.erpnext_docname) in party_mapping:
            values["erpnext_docname"] = party_mapping[("Customer", log.erpnext_docname)]
        if log.erpnext_docname in mapping:
            values["erpnext_docname"] = mapping[log.erpnext_docname]
        if log.response_json:
            original = json.loads(log.response_json)
            updated = replace(original)
            if updated != original:
                values["response_json"] = json.dumps(updated)
        if values:
            frappe.db.set_value("POS Sync Log", log.name, values, update_modified=False)
            changed += 1
    return {"updated_sync_logs": changed, "ambiguous_old_names": sorted(ambiguous)}


def audit_migration():
    from collections import defaultdict
    from frappe.model.rename_doc import get_link_fields
    from frappe.model.dynamic_links import get_dynamic_link_map
    with open(frappe.get_site_path("private", "files", "short-code-renames.json")) as stream:
        rows = json.load(stream)
    old_names = defaultdict(list)
    problems = []
    for row in rows:
        old_names[row["doctype"]].append(row["old"])
        if not frappe.db.exists(row["doctype"], row["new"]):
            problems.append(row)
    checked = 0
    for dt, old in old_names.items():
        assert not frappe.get_all(dt, filters={"name": ["in", old]}, limit=1), dt
        for field in get_link_fields(dt):
            if field.issingle:
                assert frappe.db.get_single_value(field.parent, field.fieldname) not in old
            else:
                assert not frappe.get_all(field.parent, filters={field.fieldname: ["in", old]}, limit=1), field
            checked += 1
        for field in get_dynamic_link_map().get(dt, []):
            meta = frappe.get_meta(field.parent)
            if meta.is_virtual or meta.issingle:
                continue
            assert not frappe.get_all(field.parent, filters={field.options: dt, field.fieldname: ["in", old]}, limit=1), field
            checked += 1
    assert not problems, problems
    return {"renamed": len(rows), "link_fields_checked": checked, "counts": inventory(), "passed": True}

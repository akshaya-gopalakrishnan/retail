"""Explicit migration and rollback-only checks for customer/supplier identifiers."""
import json
import re

import frappe

PARTIES = {"Customer": ("C", "customer_name"), "Supplier": ("S", "supplier_name")}


def migrate():
    from retail.short_codes import migrate_existing
    path = frappe.get_site_path("private", "files", "party-code-originals.json")
    import os
    if not os.path.exists(path):
        snapshot = {dt: frappe.get_all(dt, fields=["name", field], order_by="creation asc") for dt, (_, field) in PARTIES.items()}
        with open(path, "w") as stream:
            json.dump(snapshot, stream, indent=2)
    return migrate_existing(list(PARTIES))


def verify():
    """Two people with identical display names must get different permanent IDs."""
    results = {}
    frappe.db.savepoint("party_code_test")
    try:
        for dt, (prefix, field) in PARTIES.items():
            existing = frappe.get_all(dt, pluck="name", limit=1)
            template = frappe.get_doc(dt, existing[0]) if existing else frappe.new_doc(dt)
            values = {"doctype": dt, field: "Short Code Duplicate Name Test"}
            for key in (("customer_type", "customer_group", "territory") if dt == "Customer" else ("supplier_type", "supplier_group")):
                values[key] = template.get(key)
            first = frappe.get_doc(values).insert(ignore_permissions=True)
            second = frappe.get_doc(values).insert(ignore_permissions=True)
            assert first.name != second.name
            assert first.get(field) == second.get(field) == values[field]
            for doc in (first, second):
                assert re.fullmatch(prefix + r"-[1-9][0-9]*", doc.name), doc.name
            old_number = int(second.name.split("-")[1])
            frappe.delete_doc(dt, second.name, ignore_permissions=True, force=True)
            third = frappe.get_doc(values).insert(ignore_permissions=True)
            assert int(third.name.split("-")[1]) > old_number
            duplicate = frappe.copy_doc(third)
            duplicate.name, duplicate.docstatus = third.name, 0
            try:
                duplicate.db_insert()
            except frappe.DuplicateEntryError:
                pass
            else:
                raise AssertionError("Duplicate party code accepted")
            results[dt] = {"sample_codes": [first.name, second.name, third.name], "same_names_allowed": True, "deleted_code_not_reused": True, "duplicate_id_rejected": True}
        return results
    finally:
        frappe.db.rollback(save_point="party_code_test")


def audit():
    from retail.short_codes import audit_migration
    with open(frappe.get_site_path("private", "files", "party-code-originals.json")) as stream:
        originals = json.load(stream)
    with open(frappe.get_site_path("private", "files", "short-code-renames.json")) as stream:
        mapping = {(row["doctype"], row["old"]): row["new"] for row in json.load(stream)}
    counts = {}
    for dt, (_, field) in PARTIES.items():
        assert frappe.db.count(dt) == len(originals[dt]), dt
        for row in originals[dt]:
            new = mapping.get((dt, row["name"]), row["name"])
            assert frappe.db.get_value(dt, new, field) == row[field], (dt, new)
        counts[dt] = len(originals[dt])
    audit = audit_migration()
    return {"passed": True, "names_preserved": counts, "link_fields_checked": audit["link_fields_checked"]}

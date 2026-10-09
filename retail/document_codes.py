"""Short public identifiers for records whose native keys have system meaning."""
import json
from functools import lru_cache
from pathlib import Path

import frappe
from frappe.model.naming import getseries

FIELD = "custom_document_code"


@lru_cache(maxsize=1)
def prefixes():
    return json.loads(Path(__file__).with_name("document_code_prefixes.json").read_text())


def assign(doc, method=None):
    prefix = prefixes().get(doc.doctype)
    if prefix and doc.meta.has_field(FIELD):
        doc.set(FIELD, next_code(doc.doctype, prefix))


def next_code(doctype, prefix):
    # getseries holds the series row lock until the transaction ends. MyISAM
    # logs survive rollbacks, whereas their Series counter does not.
    while True:
        code = prefix + "-" + getseries("retail-short-code:" + prefix, 1)
        if not frappe.db.exists(doctype, {FIELD: code}):
            return code


def validate(doc, method=None):
    if doc.doctype not in prefixes() or not doc.meta.has_field(FIELD):
        return
    if doc.is_new():
        if not doc.get(FIELD):
            assign(doc)
    else:
        original = frappe.db.get_value(doc.doctype, doc.name, FIELD)
        if original and doc.get(FIELD) != original:
            frappe.throw("Document codes cannot be changed.")
        if not original and not doc.get(FIELD):
            assign(doc)


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    installed = 0
    populated = 0
    for dt, prefix in prefixes().items():
        if not frappe.db.exists("DocType", dt):
            continue
        create_custom_fields({dt: [{
            "fieldname": FIELD, "label": dt + " Code", "fieldtype": "Data",
            "insert_after": "", "read_only": 1, "no_copy": 1, "unique": 1,
            "search_index": 1, "in_list_view": 1, "in_standard_filter": 1,
        }]}, ignore_validate=True, update=False)
        frappe.db.sql("INSERT IGNORE INTO `tabSeries` (`name`, `current`) VALUES (%s, 0)", ("retail-short-code:" + prefix,))
        populated += backfill_type(dt)
        frappe.db.commit()
        installed += 1
        if installed % 25 == 0:
            print(f"Short codes: {installed} document types configured, {populated} records assigned", flush=True)
    frappe.clear_cache()
    return {"configured_types": installed, "assigned_records": populated}


def audit():
    import re
    rows = []
    seen_prefixes = set()
    for dt, prefix in prefixes().items():
        assert prefix not in seen_prefixes, prefix
        seen_prefixes.add(prefix)
        if not frappe.db.exists("DocType", dt):
            continue
        backfill_type(dt)
        values = frappe.get_all(dt, fields=["name", FIELD])
        codes = [row[FIELD] for row in values]
        assert all(code and re.fullmatch(re.escape(prefix) + r"-[1-9][0-9]*", code) for code in codes), dt
        assert len(codes) == len(set(codes)), dt
        rows.append({"doctype": dt, "prefix": prefix, "records": len(values)})
    path = frappe.get_site_path("private", "files", "document-code-coverage.json")
    with open(path, "w") as stream:
        json.dump(rows, stream, indent=2)
    return {"passed": True, "document_types": len(rows), "records": sum(row["records"] for row in rows), "coverage": path}


def boot(bootinfo):
    from retail.short_codes import PREFIXES
    bootinfo.retail_native_code_doctypes = list(PREFIXES)


def verify():
    """Verify real inserts, immutable IDs, and preserved User login identities."""
    import re
    from retail.short_codes import PREFIXES
    assert not (set(prefixes().values()) & (set(PREFIXES.values()) | {"VS"}))
    frappe.db.savepoint("document_codes_test")
    result = {}
    try:
        for dt, values in (
            ("Brand", {"brand": "Short Identifier Verification"}),
            ("User", {"email": "short-code-verification@example.invalid", "first_name": "Short Code", "send_welcome_email": 0, "enabled": 0}),
        ):
            doc = frappe.get_doc({"doctype": dt, **values}).insert(ignore_permissions=True)
            original = doc.get(FIELD)
            assert re.fullmatch(prefixes()[dt] + r"-[1-9][0-9]*", original)
            if dt == "User":
                assert doc.name == doc.email == values["email"]
            doc.set(FIELD, original + "0")
            try:
                validate(doc)
            except frappe.ValidationError:
                pass
            else:
                raise AssertionError("An existing code could be changed")
            doc.set(FIELD, original)
            duplicate = frappe.copy_doc(doc)
            duplicate.name, duplicate.docstatus = doc.name + "-duplicate", 0
            duplicate.set(FIELD, original)
            try:
                duplicate.db_insert()
            except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
                pass
            else:
                raise AssertionError("Duplicate public code accepted")
            result[dt] = {"code": original, "immutable": True, "database_unique": True}
        return result
    finally:
        frappe.db.rollback(save_point="document_codes_test")


def backfill_type(doctype):
    """Cover low-level framework inserts which intentionally bypass document hooks."""
    prefix = prefixes()[doctype]
    table = frappe.qb.DocType(doctype)
    # Fast path avoids taking a write lock when every record already has a code.
    missing = ((table[FIELD].isnull()) | (table[FIELD] == ""))
    if not frappe.qb.from_(table).select(table.name).where(missing).limit(1).run():
        return 0
    key = "retail-short-code:" + prefix
    frappe.db.sql("SELECT current FROM `tabSeries` WHERE name=%s FOR UPDATE", (key,))
    rows = frappe.qb.from_(table).select(table.name).where(missing).orderby(table.creation, table.name).for_update().run()
    if not rows:
        return 0
    updates = {row[0]: {FIELD: next_code(doctype, prefix)} for row in rows}
    frappe.db.bulk_update(doctype, updates, update_modified=False, chunk_size=500)
    return len(rows)


@frappe.whitelist()
def ensure_codes(doctype):
    if doctype not in prefixes() or not frappe.has_permission(doctype, "read"):
        frappe.throw("Not permitted", frappe.PermissionError)
    return backfill_type(doctype)


def backfill_missing():
    total = 0
    for dt in prefixes():
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": FIELD}):
            total += backfill_type(dt)
            frappe.db.commit()
    return {"assigned_records": total}

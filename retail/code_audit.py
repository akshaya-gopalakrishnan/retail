"""Inventory document identity settings across installed modules."""
import json
import frappe


def inventory():
    rows = []
    for dt in frappe.get_all('DocType', fields=['name', 'module', 'istable', 'issingle', 'is_virtual', 'autoname'], order_by='module, name'):
        if dt.istable or dt.issingle or dt.is_virtual:
            continue
        meta = frappe.get_meta(dt.name)
        try:
            count = frappe.db.count(dt.name)
        except Exception:
            count = None
        rows.append(dict(dt, count=count, title_field=meta.title_field, code_fields=[f.fieldname for f in meta.fields if 'code' in f.fieldname and f.fieldtype in ('Data', 'Int')]))
    path = frappe.get_site_path('private', 'files', 'all-document-code-audit.json')
    with open(path, 'w') as stream:
        json.dump(rows, stream, indent=2)
    return {'path': path, 'doctypes': len(rows), 'populated': [r for r in rows if r['count'] and r['module'] not in ('Core', 'Email', 'Website', 'Desk', 'Printing', 'Integrations', 'Workflow', 'Custom', 'Social', 'Automation', 'Geo', 'Contacts')]}


def migrate_business_ids():
    from retail.short_codes import migrate_existing
    import os
    path = frappe.get_site_path('private', 'files', 'remaining-business-code-originals.json')
    if not os.path.exists(path):
        fields = {
            'Employee': ['name', 'employee_name', 'user_id', 'pos_login_id'],
            'Item': ['name', 'item_name', 'custom_barcode'],
            'Driver': ['name', 'full_name'],
            'User': ['name', 'email', 'username'],
        }
        snapshot = {dt: frappe.get_all(dt, fields=[f for f in names if f == 'name' or frappe.get_meta(dt).has_field(f)]) for dt, names in fields.items()}
        with open(path, 'w') as stream:
            json.dump(snapshot, stream, indent=2)
    return migrate_existing(['Employee', 'Item', 'Driver'])


def verify_business_ids():
    from retail.short_codes import audit_migration
    with open(frappe.get_site_path('private', 'files', 'remaining-business-code-originals.json')) as stream:
        original = json.load(stream)
    with open(frappe.get_site_path('private', 'files', 'short-code-renames.json')) as stream:
        mapping = {(r['doctype'], r['old']): r['new'] for r in json.load(stream)}
    counts = {}
    for dt, rows in original.items():
        for row in rows:
            current = frappe.get_doc(dt, mapping.get((dt, row['name']), row['name']))
            for field, value in row.items():
                if field != 'name':
                    assert current.get(field) == value, (dt, current.name, field)
            if dt == 'Employee':
                assert current.employee == current.name
            if dt == 'Item':
                assert current.item_code == current.name
        counts[dt] = len(rows)
    result = audit_migration()
    return {'passed': True, 'preserved_records': counts, 'link_fields_checked': result['link_fields_checked']}

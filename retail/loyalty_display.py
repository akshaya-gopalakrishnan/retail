"""Live loyalty presentation; ledger movements remain immutable."""
import frappe
from frappe.utils import cint, getdate, today


def balances(rows, movements, as_of=None):
    cutoff = getdate(as_of or today())
    totals = {}
    for movement in movements:
        key = movement.redeem_against
        totals[key] = totals.get(key, 0) + cint(movement.loyalty_points)
    result = {}
    for row in rows:
        points = cint(row.loyalty_points)
        root = not row.redeem_against and points >= 0
        remaining = max(0, points + totals.get(row.name, 0)) if root else 0
        expired = remaining if row.expiry_date and getdate(row.expiry_date) < cutoff else 0
        available = remaining - expired
        if row.posting_date and getdate(row.posting_date) > cutoff:
            available = 0
        result[row.name] = dict(
            earned_points=points if root else 0,
            used_points=max(0, -totals.get(row.name, 0)) if root else max(0, -points),
            restored_points=max(0, points) if row.redeem_against else 0,
            remaining_points=remaining, expired_points=expired, available_points=available,
        )
    return result


@frappe.whitelist()
def get_balances(names):
    names = frappe.parse_json(names)
    if not isinstance(names, list) or len(names) > 500:
        frappe.throw('Request up to 500 loyalty entries at a time.')
    fields = ['name', 'loyalty_points', 'redeem_against', 'expiry_date', 'posting_date']
    rows = frappe.get_list('Loyalty Point Entry', filters={'name': ['in', names]},
                           fields=fields, limit_page_length=500)
    movements = frappe.get_list('Loyalty Point Entry', filters={'redeem_against': ['in', [r.name for r in rows]]},
                                fields=fields, limit_page_length=0) if rows else []
    return balances(rows, movements)


def install():
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    for prop, value, kind in [('autoname', 'field:custom_document_code', 'Data'),
                              ('title_field', 'custom_document_code', 'Data'),
                              ('show_title_field_in_link', 1, 'Check'),
                              ('search_fields', 'custom_document_code,customer,invoice', 'Data')]:
        make_property_setter('Loyalty Point Entry', None, prop, value, kind, for_doctype=True)
    make_property_setter('Loyalty Point Entry', 'loyalty_points', 'label', 'Points Movement', 'Data')
    frappe.clear_cache(doctype='Loyalty Point Entry')
    rename_entries()


def rename_entries():
    """Use assigned public codes as native keys, preserving Frappe links."""
    from retail.document_codes import backfill_type
    from frappe.model.rename_doc import rename_doc
    doctype = 'Loyalty Point Entry'
    backfill_type(doctype)
    rows = frappe.get_all(doctype, fields=['name', 'custom_document_code'])
    codes = [row.custom_document_code for row in rows]
    if len(set(codes)) != len(codes) or not all(codes):
        frappe.throw('Loyalty entry codes must be populated and unique before renaming.')
    for row in rows:
        if row.name != row.custom_document_code and frappe.db.exists(doctype, row.custom_document_code):
            frappe.throw('Loyalty entry name conflicts with code: ' + row.custom_document_code)
    for row in rows:
        if row.name != row.custom_document_code:
            rename_doc(doctype, row.name, row.custom_document_code, force=True,
                       ignore_permissions=True, show_alert=False, rebuild_search=False)

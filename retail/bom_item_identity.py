"""Retail-owned barcode display beside BOM item names."""
import frappe


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({
        'BOM': [dict(fieldname='custom_item_barcode', label='Item Barcode',
                     fieldtype='Data', insert_after='item_name', read_only=1,
                     fetch_from='item.custom_barcode')],
        'BOM Item': [dict(fieldname='custom_item_barcode', label='Item Barcode',
                          fieldtype='Data', insert_after='item_name', read_only=1,
                          fetch_from='item_code.custom_barcode', in_list_view=1, columns=2)],
    }, update=True)


@frappe.whitelist()
def get_item_identities(items):
    frappe.has_permission('BOM', 'read', throw=True)
    codes=list(dict.fromkeys(frappe.parse_json(items)))
    # Use permission-aware Item queries; no unrestricted child-table lookup.
    return frappe.get_list('Item', filters={'name': ['in', codes]},
                           fields=['name', 'item_name', 'custom_barcode'], limit_page_length=len(codes)) if codes else []

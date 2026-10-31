"""Seed editable Quick Entry defaults without overriding later customization."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


PATCH = "retail.patches.item_quick_entry_defaults"
DEFAULT_FIELDS = {
    "custom_barcode": 1,
    "custom_purchase_rate_entry": 1,
    "custom_sales_rate_entry": 1,
    "custom_purchase_tax_template": 1,
    "custom_tax": 1,
    "is_stock_item": 0,
}


def install():
    install_item_group_quick_entry()
    install_batch_valuation_default()
    _seed_defaults("retail.patches.batch_quick_entry_details", {
        "manufacturing_date": 1,
        "expiry_date": 1,
        "stock_uom": 1,
        "use_batchwise_valuation": 0,
    }, doctype="Batch")
    _seed_defaults("retail.patches.batch_valuation_full_form_only", {
        "use_batchwise_valuation": 0,
    }, doctype="Batch")
    _seed_defaults(PATCH, DEFAULT_FIELDS)
    _seed_defaults("retail.patches.item_quick_entry_brand", {"brand": 1})
    _seed_defaults("retail.patches.item_quick_entry_scale", {
        "custom_scale_item": 1,
        "custom_scale_barcode_type": 1,
    })
    _seed_defaults("retail.patches.item_quick_entry_tracking", {
        "has_batch_no": 1,
        "has_expiry_date": 1,
        "shelf_life_in_days": 1,
        "has_serial_no": 1,
    })
    for doctype in ("Customer", "Supplier"):
        _seed_defaults(
            f"retail.patches.{doctype.lower()}_quick_entry_tax_id",
            {"tax_id": 1},
            doctype=doctype,
        )


def install_item_group_quick_entry():
    patch = "retail.patches.item_group_quick_entry"
    if frappe.db.exists("Patch Log", {"patch": patch}):
        return
    make_property_setter(
        "Item Group", None, "quick_entry", 1, "Check",
        for_doctype=True, validate_fields_for_doctype=False,
    )
    _seed_defaults(patch, {
        "item_group_name": 1,
        "parent_item_group": 1,
        "is_group": 1,
    }, doctype="Item Group")


def install_batch_valuation_default():
    patch = "retail.patches.batch_valuation_opt_in"
    if frappe.db.exists("Patch Log", {"patch": patch}):
        return
    for property_name, value, property_type in (
        ("default", "0", "Text"),
        ("read_only", 0, "Check"),
    ):
        make_property_setter(
            "Batch", "use_batchwise_valuation", property_name, value, property_type,
            validate_fields_for_doctype=False,
        )
    # Native set_only_once continues to protect existing batches.
    frappe.get_doc({"doctype": "Patch Log", "patch": patch}).insert(ignore_permissions=True)
    frappe.clear_cache(doctype="Batch")


def _seed_defaults(patch, fields, doctype="Item"):
    # Run after fixture sync, once per site. Property Setters keep the defaults
    # independent of Custom Field fixtures and remain editable in Customize Form.
    if frappe.db.exists("Patch Log", {"patch": patch}):
        return
    meta = frappe.get_meta(doctype)
    if not all(meta.has_field(field) for field in fields):
        return
    for field, value in fields.items():
        make_property_setter(
            doctype, field, "allow_in_quick_entry", value, "Check",
            validate_fields_for_doctype=False,
        )
    frappe.get_doc({"doctype": "Patch Log", "patch": patch}).insert(ignore_permissions=True)
    frappe.clear_cache(doctype=doctype)

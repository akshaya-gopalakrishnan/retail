"""Compact POS receipt layout owned by Retail; preserves all document fields."""
import frappe

HEADER = [
    'customer_section', 'title', 'naming_series', 'customer', 'customer_name',
    'customer_name_in_arabic', 'tax_id', 'pos_profile', 'cost_center', 'custom_pos_business_date',
    'column_break1', 'company', 'set_warehouse', 'posting_date', 'posting_time', 'set_posting_time',
    'custom_pos_header_column', 'custom_pos_transaction_type', 'status', 'is_pos', 'is_return',
    'return_against', 'due_date', 'amended_from', 'consolidated_invoice',
    'update_billed_amount_in_sales_order', 'update_billed_amount_in_delivery_note',
]
SUMMARY = [
    'totals', 'total_qty', 'total', 'net_total', 'total_taxes_and_charges', 'total_net_weight',
    'column_break5', 'grand_total', 'rounding_adjustment', 'rounded_total', 'in_words',
    'custom_pos_totals_column', 'paid_amount', 'change_amount', 'total_advance', 'outstanding_amount',
]
BASE_TOTALS = [
    'base_total', 'base_net_total', 'base_total_taxes_and_charges', 'base_grand_total',
    'base_rounding_adjustment', 'base_rounded_total', 'base_in_words', 'base_paid_amount',
    'base_change_amount',
]
SYNC = [
    'pos_sync_section', 'external_pos_reference', 'custom_pos_completed_payload',
    'pos_bill_no', 'pos_branch', 'pos_counter', 'pos_terminal_id',
    'pos_column_break', 'pos_cashier', 'pos_cashier_employee', 'pos_shift_no',
    'pos_cashier_shift', 'pos_counter_session',
    'custom_pos_sync_column', 'pos_local_created_at', 'pos_sync_datetime',
    'pos_sync_source', 'pos_original_reference', 'custom_payment_revision',
    'custom_pos_promotion_history',
]


def onload(doc, method=None):
    doc.set_onload('retail_company_currency', frappe.get_cached_value('Company', doc.company, 'default_currency'))


def field_order(existing, section_breaks=()):
    """Move only known fields; retain every other site's additional field."""
    available = set(existing)
    accounting = ['account_for_change_amount', 'project'] if 'more_info' in available else []
    moved = set(HEADER + SUMMARY + BASE_TOTALS + SYNC + accounting)
    result = [name for name in HEADER if name in available]
    for name in existing:
        if name == 'totals':
            result.extend(field for field in SUMMARY if field in available)
        if name == 'sales_team_section_break':
            result.extend(field for field in BASE_TOTALS if field in available)
        if name not in moved:
            result.append(name)
        if name == 'more_info':
            result.extend(field for field in accounting if field in available)
    # Also support sites lacking the optional commission section.
    result.extend(name for name in BASE_TOTALS if name in available and name not in result)
    result.extend(name for name in SYNC if name in available)
    if 'edit_printing_settings' in available and section_breaks:
        relocated = []
        for section in ('accounting_dimensions_section', 'address_and_contact', 'currency_and_price_list'):
            if section not in result:
                continue
            start = result.index(section)
            end = next((index for index in range(start + 1, len(result))
                        if result[index] in section_breaks), len(result))
            relocated.extend(result[start:end])
            del result[start:end]
        target = result.index('edit_printing_settings')
        result[target:target] = relocated
    return result


def execute():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    create_custom_fields({'POS Invoice': [dict(
        fieldname=name, fieldtype='Column Break', insert_after=after,
    ) for name, after in (
        ('custom_pos_header_column', 'set_posting_time'),
        ('custom_pos_totals_column', 'rounded_total'),
        ('custom_pos_sync_column', 'pos_counter_session'),
    )]}, ignore_validate=True)
    frappe.clear_cache(doctype='POS Invoice')
    meta = frappe.get_meta('POS Invoice')

    def set_property(fieldname, prop, value, kind):
        make_property_setter('POS Invoice', fieldname, prop, value, kind,
                             validate_fields_for_doctype=False)

    for section in ('pos_sync_section', 'pricing_rule_details', 'subscription_section'):
        if meta.has_field(section):
            set_property(section, 'collapsible', 1, 'Check')
            set_property(section, 'collapsible_depends_on', 'eval:0', 'Data')
    set_property('totals', 'label', 'Totals', 'Data')
    if meta.has_field('vat_section'):
        set_property('vat_section', 'hidden', 1, 'Check')
    if meta.has_field('accounting_dimensions_section'):
        set_property('accounting_dimensions_section', 'hidden', 1, 'Check')
    for name, reference, detail in (
        ('update_billed_amount_in_sales_order', 'sales_order', 'so_detail'),
        ('update_billed_amount_in_delivery_note', 'delivery_note', 'dn_detail'),
    ):
        if meta.has_field(name):
            condition = ('eval:doc.is_return && doc.return_against && '
                         f'(doc.items || []).some(function(row) {{return row.{reference} || row.{detail};}})')
            set_property(name, 'depends_on', condition, 'Data')
    order = field_order([field.fieldname for field in meta.fields], {
        field.fieldname for field in meta.fields if field.fieldtype in ('Section Break', 'Tab Break')
    })
    make_property_setter('POS Invoice', None, 'field_order', frappe.as_json(order), 'Data',
                         for_doctype=True, validate_fields_for_doctype=False)
    frappe.clear_cache(doctype='POS Invoice')

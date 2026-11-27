"""Permanent company-scoped trading bill numbers, separate from document names."""
import re

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.naming import getseries
from frappe.utils import cint, getdate, nowdate

FIELD = 'custom_bill_number'
SNAPSHOT_FIELDS = (FIELD, 'custom_bill_sequence', 'custom_bill_date', 'custom_bill_company_abbr', 'custom_bill_vat_enabled')


def format_number(abbreviation, date, vat_enabled, sequence):
    return f'{abbreviation}{getdate(date):%y}{int(bool(vat_enabled))}00{int(sequence):02d}'


def print_layout(html):
    return re.sub(r'(<td class="detail-value">\s*){{ doc.name }}(\s*</td>)',
                  r'\1{{ doc.get("custom_bill_number") or doc.name }}\2', html)


def ensure_setup():
    create_custom_fields({'Sales Invoice': [
        {'fieldname': FIELD, 'label': 'Bill Number', 'fieldtype': 'Data',
         'insert_after': 'customer', 'read_only': 1, 'no_copy': 1, 'unique': 1, 'search_index': 1},
        {'fieldname': 'custom_bill_sequence', 'label': 'Bill Sequence', 'fieldtype': 'Data',
         'insert_after': FIELD, 'hidden': 1, 'read_only': 1, 'no_copy': 1},
        {'fieldname': 'custom_bill_date', 'label': 'Bill Generation Date', 'fieldtype': 'Date',
         'insert_after': 'custom_bill_sequence', 'hidden': 1, 'read_only': 1, 'no_copy': 1},
        {'fieldname': 'custom_bill_company_abbr', 'label': 'Bill Company Abbreviation', 'fieldtype': 'Data',
         'insert_after': 'custom_bill_date', 'hidden': 1, 'read_only': 1, 'no_copy': 1},
        {'fieldname': 'custom_bill_vat_enabled', 'label': 'Bill VAT Enabled', 'fieldtype': 'Check',
         'insert_after': 'custom_bill_company_abbr', 'hidden': 1, 'read_only': 1, 'no_copy': 1},
    ]}, ignore_validate=True)
    if frappe.db.exists('Print Format', 'Sales Invoice - A4'):
        original = frappe.db.get_value('Print Format', 'Sales Invoice - A4', 'html') or ''
        html = print_layout(original)
        if html != original:
            frappe.db.set_value('Print Format', 'Sales Invoice - A4', 'html', html)
            frappe.clear_document_cache('Print Format', 'Sales Invoice - A4')


def set_bill_title(doc):
    if doc.get('is_pos') or doc.get('is_consolidated') or not doc.meta.has_field(FIELD):
        return
    if not doc.is_new():
        # Ignore client-supplied changes, including attempts to alter snapshots.
        saved = frappe.db.get_value('Sales Invoice', doc.name, list(SNAPSHOT_FIELDS), as_dict=True)
        if saved:
            doc.update(saved)
        if doc.get(FIELD):
            doc.title = doc.get(FIELD)
        return
    values = doc.flags.get('retail_bill_number')
    if not values:
        # Serializes first-use series creation as well as subsequent allocation.
        company = frappe.db.get_value('Company', doc.company, ['name', 'abbr'], as_dict=True, for_update=True)
        if not company or not company.abbr:
            frappe.throw(frappe._('Set the Company abbreviation before generating a Bill Number.'))
        from retail.domains.transactions.trading_vat import vat_disabled
        date = nowdate()
        enabled = not vat_disabled(doc)
        key = 'retail-trading-bill:' + company.name
        while True:
            sequence = getseries(key, 2)
            number = format_number(company.abbr, date, enabled, sequence)
            if not frappe.db.exists('Sales Invoice', {FIELD: number}):
                break
        values = dict(zip(SNAPSHOT_FIELDS, (number, sequence, date, company.abbr, cint(enabled))))
        doc.flags.retail_bill_number = values
    doc.update(values)
    doc.title = doc.get(FIELD)

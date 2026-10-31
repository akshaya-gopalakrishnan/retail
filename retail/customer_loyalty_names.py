"""Stable numeric names for the read-only customer loyalty balance records."""
import hashlib

import frappe
from frappe.model.naming import getseries


def key(company, customer):
    return 'Customer Loyalty Balance:' + hashlib.sha256(f'{company}\0{customer}'.encode()).hexdigest()


def ensure_name(company, customer):
    if not company or not customer:
        return
    mapping = key(company, customer)
    if frappe.db.sql('select current from `tabSeries` where name=%s', mapping):
        return
    # Use Frappe's naming lock. Existing customer names are never renumbered.
    number = int(getseries('Customer Loyalty Balance', 1))
    frappe.db.sql('insert ignore into `tabSeries` (name, current) values (%s, %s)', (mapping, number))


def on_entry(doc, method=None):
    ensure_name(doc.company, doc.customer)


def install():
    rows = frappe.get_all('Loyalty Point Entry', fields=['company', 'customer'],
        group_by='company, customer', order_by='company, customer', limit_page_length=0)
    for row in rows:
        ensure_name(row.company, row.customer)


def names(rows):
    pairs = {(row['company'], row['customer']) for row in rows}
    if not pairs:
        return {}
    keys = {key(*pair): pair for pair in pairs}
    saved = frappe.db.sql('select name, current from `tabSeries` where name in %s', (tuple(keys),))
    result = {keys[name]: str(number) for name, number in saved}
    if len(result) != len(pairs):
        frappe.throw('Customer loyalty numbering needs synchronization. Run the Retail migration.')
    return result

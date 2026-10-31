"""Resolve invoice-date loyalty eligibility for existing and new customers."""
import frappe
from frappe.utils import getdate


def matches_tree(doctype, selected, actual):
    if not selected:
        return True
    if not actual:
        return False
    if selected == actual:
        return True
    parent = frappe.get_cached_value(doctype, selected, ['lft', 'rgt'], as_dict=True)
    child = frappe.get_cached_value(doctype, actual, ['lft', 'rgt'], as_dict=True)
    return bool(parent and child and parent.lft <= child.lft and child.rgt <= parent.rgt)


def resolve(customer, company, posting_date):
    if not customer or not company:
        return None
    customer = frappe.db.get_value('Customer', customer,
        ['name', 'loyalty_program', 'customer_group', 'territory', 'disabled'], as_dict=True)
    if not customer or customer.disabled:
        return None
    programs = frappe.get_all('Loyalty Program', filters={'company': company},
        fields=['name', 'from_date', 'to_date', 'auto_opt_in', 'customer_group', 'customer_territory'],
        order_by='from_date desc, creation desc, name desc', limit_page_length=0)
    return select_program(customer, programs, posting_date)


def select_program(customer, programs, posting_date):
    """Programs must be company-scoped and newest-first; usable in bulk snapshots."""
    if not customer or customer.get("disabled"):
        return None
    date = getdate(posting_date)
    for program in programs:
        if not program.auto_opt_in and program.name != customer.loyalty_program:
            continue
        if ((program.from_date and date < getdate(program.from_date))
                or (program.to_date and date > getdate(program.to_date))):
            continue
        if (matches_tree('Customer Group', program.customer_group, customer.customer_group)
                and matches_tree('Territory', program.customer_territory, customer.territory)):
            return program.name
    return None


def prepare_invoice(doc):
    # Returns retain the original program; consolidation must never earn twice.
    if doc.get('is_return') or doc.get('is_consolidated') or not doc.customer:
        return
    if doc.get('redeem_loyalty_points') and doc.get('loyalty_program'):
        return
    program = resolve(doc.customer, doc.company, doc.posting_date)
    doc.loyalty_program = program
    if program and frappe.db.get_value('Customer', doc.customer, 'loyalty_program') != program:
        # Keep ERPNext's enrollment and tier APIs consistent with the selected program.
        frappe.db.set_value('Customer', doc.customer,
            {'loyalty_program': program, 'loyalty_program_tier': None})

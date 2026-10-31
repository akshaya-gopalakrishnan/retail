"""Customer/program balances without exposing invoice-by-invoice rows."""
from collections import defaultdict

import frappe
from frappe.utils import getdate, today

from retail.loyalty import available_buckets
from retail.promotions.pos_download import _loyalty_point_totals


def summarize(entries, as_of):
    groups = defaultdict(list)
    for entry in entries:
        if entry.posting_date and getdate(entry.posting_date) <= getdate(as_of):
            groups[(entry.company, entry.customer, entry.loyalty_program)].append(entry)
    result = []
    for (company, customer, program), movements in sorted(groups.items()):
        totals = _loyalty_point_totals(movements, as_of)
        result.append(dict(company=company, customer=customer, loyalty_program=program,
            **totals, available_points=sum(balance for _, balance in available_buckets(movements, as_of)),
            creation=min((entry.creation for entry in movements if entry.get('creation')), default=None),
            modified=max((entry.modified for entry in movements if entry.get('modified')), default=None),
            as_of_date=as_of))
    return result


def get_entries(company, customer=None, loyalty_program=None):
    """Read authorized ledger rows for both totals and invoice detail forms."""
    from retail.sidebar_permissions import require_target

    frappe.has_permission('Loyalty Point Entry', 'read', throw=True)
    require_target('doctype', 'Loyalty Point Entry')
    frappe.get_doc('Company', company).check_permission('read')
    filters = dict(company=company)
    for field, value in (('customer', customer), ('loyalty_program', loyalty_program)):
        if value:
            filters[field] = value
    # get_list applies native record/user permissions before aggregation.
    return frappe.get_list('Loyalty Point Entry', filters=filters,
        fields=['name', 'company', 'customer', 'loyalty_program', 'loyalty_points',
            'redeem_against', 'posting_date', 'expiry_date', 'invoice_type', 'invoice', 'creation', 'modified'],
        limit_page_length=0)


@frappe.whitelist()
def get_summary(company, customer=None, loyalty_program=None):
    entries = get_entries(company, customer, loyalty_program)
    result = summarize(entries, today())
    customers = list({row['customer'] for row in result})
    names = {row.name: row.customer_name for row in frappe.get_list('Customer',
        filters={'name': ['in', customers]}, fields=['name', 'customer_name'],
        limit_page_length=0)} if customers else {}
    for row in result:
        row['customer_name'] = names.get(row['customer'], '')
    return result

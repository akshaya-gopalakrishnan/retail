"""Read-only, company-scoped promotion snapshots for POS customer masters."""
from collections import defaultdict

import frappe
from frappe.utils import flt, nowdate

from retail.loyalty import available_buckets
from retail.promotions.pos_download import _loyalty_point_totals, active_loyalty_entries


def add_customer_promotions(customers, company):
    if not customers:
        return
    names = [row['name'] for row in customers]
    as_of = nowdate()
    currency = frappe.get_cached_value('Company', company, 'default_currency')
    assignments = {row.name: row for row in frappe.get_all('Customer',
        filters={'name': ['in', names]},
        fields=['name', 'loyalty_program', 'loyalty_program_tier', 'customer_group', 'territory', 'disabled'], limit_page_length=0)}
    programs = {row.name: row for row in frappe.get_all('Loyalty Program',
        filters={'company': company}, fields=['name', 'loyalty_program_name', 'conversion_factor',
            'from_date', 'to_date', 'auto_opt_in', 'customer_group', 'customer_territory'],
        order_by='from_date desc, creation desc, name desc', limit_page_length=0)}
    entries = defaultdict(list)
    for entry in frappe.get_all('Loyalty Point Entry',
        filters={'company': company, 'customer': ['in', names]},
        fields=['name', 'customer', 'company', 'loyalty_program', 'loyalty_program_tier',
            'loyalty_points', 'purchase_amount', 'posting_date', 'expiry_date',
            'redeem_against', 'invoice_type', 'invoice', 'modified'],
        order_by='posting_date, name', limit_page_length=0):
        entries[entry.customer].append(entry)
    vouchers = defaultdict(list)
    # Only customer-linked vouchers; unassigned cards never belong to a customer snapshot.
    for voucher in frappe.get_all('Gift Voucher Ledger',
        filters={'company': company, 'customer': ['in', names]},
        fields=['name', 'voucher_code', 'customer', 'voucher_amount', 'balance_amount', 'status',
            'issued_date', 'expiry_date', 'promotion', 'issued_against_type', 'issued_against',
            'redeemed_against_type', 'redeemed_against', 'redeemed_date', 'company', 'warehouse',
            'currency', 'voucher_kind', 'voucher_card_batch', 'valid_from', 'card_blocked',
            'card_archived', 'use_redemption_hours', 'active_from_time', 'active_to_time', 'modified'],
        order_by='issued_date, name', limit_page_length=0):
        from retail.api.gift_vouchers import invalid_reason
        reason = invalid_reason(voucher)
        voucher.update(valid=not reason, reason=reason)
        vouchers[voucher.customer].append(voucher)
    for customer in customers:
        assignment = assignments.get(customer['name']) or frappe._dict()
        from retail.loyalty_enrollment import select_program
        program = programs.get(select_program(assignment, list(programs.values()), as_of))
        movements = active_loyalty_entries(entries[customer['name']], as_of)
        balances = []
        program_names = {entry.loyalty_program for entry in movements}
        if program:
            program_names.add(program.name)
        for name in sorted(program_names):
            group = [entry for entry in movements if entry.loyalty_program == name]
            totals = _loyalty_point_totals(group, as_of)
            totals['available_points'] = sum(balance for _, balance in available_buckets(group, as_of))
            factor = flt(programs[name].conversion_factor) if name in programs else 0
            balances.append(dict(loyalty_program=name, **totals, conversion_factor=factor,
                redeemable_amount=flt(totals['available_points'] * factor), currency=currency,
                as_of_date=as_of))
        customer.update(
            loyalty_program=program.name if program else None,
            loyalty_program_name=program.loyalty_program_name if program else None,
            loyalty_program_tier=(assignment.get('loyalty_program_tier')
                if program and program.name == assignment.get('loyalty_program') else None),
            loyalty_conversion_factor=flt(program.conversion_factor) if program else 0,
            loyalty_balances=balances, loyalty_point_entries=movements,
            gift_vouchers=vouchers[customer['name']], promotions_as_of=as_of)

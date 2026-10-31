"""Promotion-only additions to the existing completed POS payment rows.

Original payloads are immutable. New promotion tenders use server-owned accounts;
source balances are comparisons, never permission to rewrite a completed bill.
"""
import hashlib
import json

import frappe
from frappe.utils import cint, flt, getdate

MODES = ('Loyalty', 'Promotion Voucher', 'Voucher Card')
OPERATION = 'POS Promotion Redemption'


def mode(row):
    value = row.get('mode_of_payment') or row.get('mode') or row.get('mop')
    if isinstance(value, str) and value.strip().lower() == 'loyalty':
        return 'Loyalty'
    if not value and flt(row.get('points')) > 0:
        return 'Loyalty'
    return value


def rows(payload):
    return [(index, row) for index, row in enumerate(payload.get('payments') or []) if mode(row) in MODES]


def total(payload):
    return sum(flt(row.get('amount')) for _, row in rows(payload))


def validate(payload):
    """Only unreadable numeric values fail; source/eligibility differences are audited."""
    from retail.pos_settlements import amount
    for _, row in rows(payload):
        amount(row.get('amount'))
        if row.get('points') is not None:
            amount(row['points'])


def account(company, payment_mode, reference=None):
    """Never choose a cash/bank account from terminal input."""
    frappe.db.get_value('Company', company, 'name', for_update=True)
    configured = frappe.db.get_value('Mode of Payment Account',
        {'parent': payment_mode, 'company': company}, 'default_account')
    if payment_mode != "Loyalty" and configured and frappe.get_cached_value('Account', configured, 'company') == company:
        return configured
    selected = None
    if payment_mode == 'Loyalty' and reference:
        program = frappe.db.get_value('Loyalty Program', reference, ['company', 'expense_account'], as_dict=True)
        if program and program.company == company:
            selected = program.expense_account
    if not selected and configured and frappe.get_cached_value('Account', configured, 'company') == company:
        selected = configured
    if not selected:
        name = 'Retail POS Promotion Redemptions'
        selected = frappe.db.get_value('Account', {'company': company, 'account_name': name}, 'name')
        if not selected:
            parent = frappe.db.get_value('Account', {'company': company, 'root_type': 'Expense', 'is_group': 1}, 'name')
            selected = frappe.get_doc(dict(doctype='Account', account_name=name, company=company,
                parent_account=parent, is_group=0, root_type='Expense', report_type='Profit and Loss')).insert(ignore_permissions=True).name
    if not frappe.db.exists('Mode of Payment', payment_mode):
        frappe.get_doc(dict(doctype='Mode of Payment', mode_of_payment=payment_mode, type='General',
            enabled=1, accounts=[dict(company=company, default_account=selected)])).insert(ignore_permissions=True)
    return selected


def native_payments(payload, counter):
    result = []
    for _, row in rows(payload):
        reference = row.get('reference_no')
        if mode(row) == 'Loyalty':
            reference = reference or _assigned_active_program(payload.get('customer') or counter.get('default_customer'), counter.company,
                payload.get('posting_date') or frappe.utils.today())
        result.append(dict(mode_of_payment=mode(row), amount=flt(row.get('amount')),
            reference_no=row.get('reference_no'),
            account=account(counter.company, mode(row), reference)))
    difference = total_difference(payload)
    if difference:
        result.append(dict(mode_of_payment='Promotion Variance', amount=difference,
            reference_no=payload.get('external_pos_reference'),
            account=account(counter.company, 'Promotion Variance')))
    return result


def total_difference(payload):
    if not rows(payload):
        return 0
    from retail.pos_settlements import settlements, cash_payments
    allocations = settlements(payload)
    requested = sum(flt(row['requested_amount']) for row in allocations)
    tender = sum(flt(row.get('amount')) for row in cash_payments(payload)) + total(payload)
    legacy_loyalty = flt((payload.get('loyalty_redemption') or {}).get('amount'))
    return flt(flt(payload.get('rounded_total', payload.get('grand_total'))) - tender - requested - legacy_loyalty, 2)


def allow_internal_variance(doc, check):
    """The only negative sale tender allowed here is the server-derived variance."""
    saved = [(row, row.amount) for row in doc.get('payments') or []
        if row.mode_of_payment == 'Promotion Variance' and flt(row.amount) < 0]
    try:
        for row, _ in saved:
            row.amount = 0
        return check()
    finally:
        for row, value in saved:
            row.amount = value


def audit(doc, index, row, reason, expected=None):
    from retail.pos_rate_audit import insert_audit, audit_cashier_fields
    value = flt(row.get('amount'))
    comparison = expected or {}
    insert_audit(doc, dict(reason=f'Offline POS payment {index + 1} ({mode(row)}): {reason}. '
        'Completed sale and intended payment retained.', promo_reference=row.get('reference_no'),
        pos_gross_amount=value, erp_expected_gross_amount=flt(comparison.get('amount')),
        amount_difference=value-flt(comparison.get('amount')),
        pos_calculation_json=json.dumps(dict(payment_row=index + 1, **row), default=str),
        erp_calculation_json=json.dumps(comparison, default=str), **audit_cashier_fields(doc)))


def redeem_payment_loyalty(doc):
    """Redeem this receipt's loyalty tenders once, before earning new points."""
    if doc.is_return or doc.flags.get("payment_loyalty_redeemed"):
        return
    payload = frappe.parse_json(doc.get('custom_pos_completed_payload') or '{}')
    payments = [(index, row) for index, row in rows(payload) if mode(row) == 'Loyalty']
    if not payments:
        return
    from retail import loyalty
    loyalty.lock_customer(doc)
    if not frappe.db.exists('Loyalty Point Entry', {
        'invoice_type': doc.doctype, 'invoice': doc.name, 'loyalty_points': ['<', 0]
    }):
        for index, row in payments:
            _loyalty(doc, index, row)
    doc.flags.payment_loyalty_redeemed = True


def apply(doc):
    payload = frappe.parse_json(doc.get('custom_pos_completed_payload') or '{}')
    if not rows(payload) or doc.is_return:
        return
    from retail import pos_operations
    difference = total_difference(payload)
    if difference:
        audit(doc, -1, dict(mode_of_payment='Promotion Variance', amount=difference,
            reference_no=doc.external_pos_reference), 'Payment portions differ from the recorded bill total; '
            'explicit promotion variance posted without changing customer credit', {'amount': 0})
    for index, row in rows(payload):
        if mode(row) == 'Loyalty':
            redeem_payment_loyalty(doc)
            continue
        reference = 'PROMO-' + hashlib.sha256(f'{doc.external_pos_reference}:{index}'.encode()).hexdigest()
        request = dict(company=doc.company, customer=doc.customer, invoice=doc.name,
            payment_row=index + 1, payment=row)
        def effect(index=index, row=row):
            _voucher(doc, index, row)
            return dict(status='Success', invoice_name=doc.name, doctype=doc.doctype, amount=flt(row.get('amount')))
        pos_operations.execute(OPERATION, reference, request, effect,
            log_type=OPERATION)


def _voucher(doc, index, row):
    code = row.get('reference_no')
    if not code or not frappe.db.exists('Gift Voucher Ledger', code):
        audit(doc, index, row, 'Voucher source was not found', {'amount': 0, 'source_missing': True})
        return
    voucher = frappe.get_doc('Gift Voucher Ledger', code, for_update=True)
    if voucher.company != doc.company:
        audit(doc, index, row, 'Voucher belongs to another company; source retained there', {'amount': 0, 'company': voucher.company})
        return
    from retail.api.gift_vouchers import invalid_reason
    reasons = []
    reason = invalid_reason(voucher)
    if reason:
        reasons.append(reason)
    expected_kind = 'Voucher Card' if voucher.get('voucher_card_batch') else 'Promotion Voucher'
    if mode(row) != expected_kind:
        reasons.append('Voucher type differs from the POS MOP')
    if voucher.get('customer') and voucher.customer != doc.customer:
        reasons.append('Voucher customer differs from the sale customer')
    if voucher.get('warehouse') and voucher.warehouse != doc.set_warehouse:
        reasons.append('Voucher warehouse differs from the sale warehouse')
    value, before = flt(row.get('amount')), flt(voucher.balance_amount)
    if value > before:
        reasons.append('Requested redemption exceeds the ERP balance')
    if voucher.get('voucher_card_batch'):
        from retail.voucher_cards import eligible_amount
        eligible = eligible_amount(voucher, doc.items, doc.grand_total)
        if value > eligible:
            reasons.append('Requested redemption exceeds eligible items')
    if voucher.get('currency') and voucher.currency != doc.currency:
        reasons.append('Voucher currency differs from the sale currency')
    if reasons:
        audit(doc, index, row, '; '.join(reasons), {'amount': before, 'balance_before': before,
            'balance_after': flt(before-value, 2), 'status': voucher.status})
    # Completed offline redemption can expose a negative source balance. Keep the
    # exact movement and its audit instead of inventing extra customer credit.
    frappe.db.set_value('Gift Voucher Ledger', code, dict(balance_amount=flt(before-value, 2),
        status='Redeemed' if before-value <= 0 else 'Partially Used', redeemed_date=doc.posting_date,
        redeemed_against_type=doc.doctype, redeemed_against=doc.name))
    if voucher.get('voucher_card_batch'):
        from retail.voucher_cards import record
        record(voucher, 'Redeemed', value, doc.external_pos_reference)


def _assigned_active_program(customer, company, posting_date):
    from retail.loyalty_enrollment import resolve
    return resolve(customer, company, posting_date)


def _loyalty(doc, index, row):
    reference = row.get('reference_no')
    if not reference:
        reference = _assigned_active_program(doc.customer, doc.company, doc.posting_date)
    if not reference or not frappe.db.exists('Loyalty Program', reference):
        audit(doc, index, row, 'Loyalty program source was not found', {'source_missing': True})
        return
    program = frappe.get_doc('Loyalty Program', reference)
    if program.company != doc.company:
        audit(doc, index, row, 'Loyalty program belongs to another company; source retained there', {'company': program.company})
        return
    from retail import loyalty
    loyalty.lock_customer(doc)
    entries = loyalty.ledger_entries(doc.customer, program.name, doc.company, lock=True)
    entries = [entry for entry in entries if not (entry.invoice_type == doc.doctype
        and entry.invoice == doc.name and entry.loyalty_points >= 0)]
    buckets = loyalty.available_buckets(entries, doc.posting_date)
    balance = sum(n for _, n in buckets)
    points = row.get('points')
    reasons = []
    if points is None:
        points = flt(row.get('amount')) / flt(program.conversion_factor) if flt(program.conversion_factor) else 0
        reasons.append('Point count omitted; derived from the downloaded program conversion')
    count = cint(points)
    if count != flt(points) or count <= 0:
        audit(doc, index, row, 'Point count is not a positive whole number; monetary settlement retained', {'points': points})
        return
    if count > balance:
        reasons.append('Requested points exceed the available ERP balance')
    expected = flt(count * flt(program.conversion_factor), 2)
    if expected != flt(row.get('amount'), 2):
        reasons.append('POS money value differs from the current conversion factor')
    if frappe.db.get_value('Customer', doc.customer, 'loyalty_program') != program.name:
        reasons.append('Customer enrollment differs from the saved POS program')
    if ((program.from_date and getdate(doc.posting_date) < getdate(program.from_date))
            or (program.to_date and getdate(doc.posting_date) > getdate(program.to_date))):
        reasons.append('Program dates differ from the completed sale date')
    if reasons:
        audit(doc, index, row, '; '.join(reasons), {'amount': expected, 'available_points': balance,
            'requested_points': count, 'conversion_factor': program.conversion_factor})
    remaining = count
    movements = []
    for bucket, available in buckets:
        used = min(remaining, available)
        if used:
            movements.append([bucket, used])
            remaining -= used
        if not remaining:
            break
    if remaining:
        roots = [entry for entry in entries if not entry.redeem_against and entry.loyalty_points > 0]
        movements.append([roots[0] if roots else None, remaining])
    for bucket, used in movements:
        frappe.get_doc(dict(doctype='Loyalty Point Entry', company=doc.company, customer=doc.customer,
            loyalty_program=program.name, loyalty_program_tier=bucket.loyalty_program_tier if bucket else None,
            invoice_type=doc.doctype, invoice=doc.name, redeem_against=bucket.name if bucket else None,
            loyalty_points=-used, purchase_amount=0, posting_date=doc.posting_date,
            expiry_date=bucket.expiry_date if bucket else doc.posting_date)).insert(ignore_permissions=True)

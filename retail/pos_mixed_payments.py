"""Additive completed-sale loyalty and multiple approved voucher redemptions."""
import math

import frappe
from frappe.utils import flt


def voucher_rows(payload):
    if 'voucher_redemptions' in payload and payload.get('voucher_redemption'):
        frappe.throw('Send voucher_redemptions or voucher_redemption, not both.')
    rows = payload.get('voucher_redemptions')
    if rows is None:
        return [payload['voucher_redemption']] if payload.get('voucher_redemption') else []
    if not isinstance(rows, list):
        frappe.throw('voucher_redemptions must be a list.')
    return rows


def loyalty_amount(payload):
    row = payload.get('loyalty_redemption')
    if row is None:
        return 0
    if not isinstance(row, dict):
        frappe.throw('loyalty_redemption must be an object.')
    from retail.pos_settlements import amount
    points = row.get('points')
    try:
        points = float(points)
    except (ValueError, TypeError):
        frappe.throw('Loyalty points must be a positive whole number.')
    if not math.isfinite(points) or points <= 0 or points != int(points):
        frappe.throw('Loyalty points must be a positive whole number.')
    value = amount(row.get('amount'))
    if not row.get('loyalty_program') or value <= 0:
        frappe.throw('Loyalty redemption requires loyalty_program, points and a positive amount.')
    return value


def validate(payload, is_return=False):
    rows = voucher_rows(payload)
    value = loyalty_amount(payload)
    if is_return and (payload.get("voucher_redemptions") or value):
        frappe.throw('Send redemptions on sales only, not on return invoices.')
    from retail.pos_settlements import amount
    if rows and 'voucher_redemptions' in payload and payload.get('bill_total_before_vouchers') is None:
        frappe.throw('Send bill_total_before_vouchers with voucher_redemptions so vouchers are deducted exactly once.')
    seen_codes, seen_refs = set(), set()
    for row in rows if 'voucher_redemptions' in payload else []:
        if not isinstance(row, dict):
            frappe.throw('Each voucher redemption must be an object.')
        code, reference = row.get('voucher_code'), row.get('redemption_reference')
        if not isinstance(code, str) or not code or not isinstance(reference, str) or not reference:
            frappe.throw('Each voucher requires voucher_code, amount and its approved redemption_reference.')
        if code in seen_codes or reference in seen_refs:
            frappe.throw('Send each voucher and approval reference only once per invoice.')
        seen_codes.add(code)
        seen_refs.add(reference)
        if amount(row.get('amount')) <= 0:
            frappe.throw('Voucher redemption amount must be positive.')
    if value or 'voucher_redemptions' in payload:
        if payload.get('grand_total') is None:
            frappe.throw('Mixed redemption invoices require grand_total.')
        if payload.get('bill_total_before_vouchers') is not None:
            total = amount(payload['bill_total_before_vouchers'])
            if flt(total - sum(amount(r['amount']) for r in rows), 2) != amount(payload['grand_total']):
                frappe.throw('grand_total must equal bill_total_before_vouchers minus voucher benefits.')
    return value


def set_loyalty(doc, payload):
    if not payload.get('loyalty_redemption'):
        return
    value = loyalty_amount(payload)
    row = payload['loyalty_redemption']
    program = frappe.get_doc('Loyalty Program', row['loyalty_program'])
    if program.company != doc.company:
        frappe.throw('Loyalty Program belongs to another company.')
    doc.redeem_loyalty_points = 1
    doc.loyalty_program = program.name
    doc.loyalty_points = int(float(row['points']))
    doc.loyalty_amount = value
    doc.loyalty_redemption_account = program.expense_account
    doc.loyalty_redemption_cost_center = program.cost_center


def validate_loyalty(doc, payload):
    """Use Retail's bucket ledger; never let a mismatched money amount post."""
    from retail import loyalty
    requested = loyalty_amount(payload)
    loyalty.lock_customer(doc)
    loyalty.validate_redemption(doc)
    if flt(doc.loyalty_amount, 2) != requested:
        frappe.throw('Loyalty amount does not match points and the program conversion factor.')
    from retail.pos_completed_sale import restore
    restore(doc)

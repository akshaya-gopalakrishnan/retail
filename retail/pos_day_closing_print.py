"""Read-only day-closing print data. Never refresh or save a closing here."""
import json
from collections import defaultdict

import frappe
from frappe.utils import flt


def _json(value):
    if isinstance(value, dict):
        return value
    try:
        result = json.loads(value or '{}')
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError):
        return {}


def aggregate(invoices, payments, closing):
    """Aggregate submitted source documents; preserve the closing's saved totals."""
    sales = dict(item_sales=0.0, item_refund=0.0, discount=0.0, tax=0.0, round_off=0.0)
    modes, counters, cashiers, categories = (defaultdict(float) for _ in range(4))
    tax_rows = {}
    for invoice in invoices:
        net = flt(invoice.get('net_total'))
        sales['item_refund' if invoice.get('is_return') else 'item_sales'] += net
        sales['discount'] += flt(invoice.get('discount_amount'))
        sales['tax'] += flt(invoice.get('total_taxes_and_charges'))
        sales['round_off'] += flt(invoice.get('rounding_adjustment'))
        change = flt(invoice.get('change_amount'))
        invoice_collections = 0.0
        for payment in invoice.get('payments', []):
            amount = flt(payment.get('amount'))
            if change and payment.get('account') == invoice.get('account_for_change_amount'):
                amount -= change
                change = 0
            modes[payment.get('mode_of_payment') or 'Unspecified'] += amount
            invoice_collections += amount
        counters[invoice.get('pos_counter') or 'Unspecified'] += invoice_collections
        cashiers[invoice.get('pos_cashier_shift') or 'Unspecified'] += invoice_collections
        taxable = defaultdict(float)
        for item in invoice.get('items', []):
            categories[item.get('item_group') or 'Unspecified'] += flt(item.get('net_amount'))
            taxable[item.get('item_code') or item.get('item_name')] += flt(item.get('net_amount'))
        for tax in invoice.get('taxes', []):
            details = _json(tax.get('item_wise_tax_detail'))
            label = tax.get('description') or tax.get('account_head') or 'Tax'
            sign = -1 if tax.get('add_deduct_tax') == 'Deduct' else 1
            if details:
                for key, detail in details.items():
                    if not isinstance(detail, (list, tuple)) or len(detail) < 2:
                        continue
                    rate = flt(detail[0])
                    group = (label, rate)
                    row = tax_rows.setdefault(group, dict(label=label, rate=rate, taxable=0.0, amount=0.0))
                    if tax.get('charge_type') == 'On Net Total':
                        if row['taxable'] is not None:
                            row['taxable'] += taxable.get(key, 0)
                    else:
                        row['taxable'] = None
                    row['amount'] += sign * flt(detail[1]) / (flt(invoice.get('conversion_rate')) or 1)
            else:
                rate = flt(tax.get('rate'))
                row = tax_rows.setdefault((label, rate), dict(label=label, rate=rate, taxable=0.0, amount=0.0))
                if tax.get('charge_type') == 'On Net Total':
                    if row['taxable'] is not None:
                        row['taxable'] += net
                else:
                    row['taxable'] = None
                value = tax.get('tax_amount_after_discount_amount')
                row['amount'] += sign * flt(tax.get('tax_amount') if value is None else value)
        if not invoice.get('taxes'):
            row = tax_rows.setdefault(('No Tax', 0), dict(label='No Tax', rate=0, taxable=0.0, amount=0.0))
            row['taxable'] += net
    for payment in payments:
        amount = flt(payment.get('received_amount')) if payment.get('payment_type') == 'Receive' else -flt(payment.get('paid_amount'))
        modes[payment.get('mode_of_payment') or 'Unspecified'] += amount
        counters[payment.get('pos_counter') or 'Unspecified'] += amount
        cashiers[payment.get('pos_cashier_shift') or 'Unspecified'] += amount
    saved_modes = _json(closing.get('payment_totals'))
    settlements = _json(closing.get('pos_settlement_totals'))
    for field in ('credit_sales', 'credit_notes_issued', 'credit_notes_redeemed', 'credit_notes_applied', 'credit_notes_unresolved'):
        if field not in settlements and closing.get('pos_' + field) is not None:
            settlements[field] = flt(closing.get('pos_' + field))
    warnings = []
    if len(invoices) != int(closing.get('total_invoice_count') or 0) or abs(sum(flt(i.get('grand_total')) for i in invoices) - flt(closing.get('total_sales'))) > 0.01:
        warnings.append('Invoice breakdown differs from the saved closing totals. Saved totals are preserved.')
    if saved_modes and any(abs(flt(saved_modes.get(key)) - modes.get(key, 0)) > 0.01 for key in set(saved_modes) | set(modes)):
        warnings.append('Collection breakdown differs from the saved Payment Method Totals. Saved totals are preserved.')
    if not saved_modes:
        warnings.append('Payment Method Totals were not saved on this closing; collections below are derived from linked submitted documents.')
    category_total = sum(categories.values())
    return dict(sales=sales, modes=saved_modes or dict(modes), collection_total=sum(flt(x) for x in (saved_modes or modes).values()),
                counter_collections=dict(counters), cashier_collections=dict(cashiers),
                categories=[dict(label=k, amount=v, percentage=v / category_total * 100 if category_total else 0) for k, v in sorted(categories.items())],
                category_total=category_total, taxes=list(tax_rows.values()), settlements=settlements, warnings=warnings)


def day_closing_print_data(doc):
    if doc.doctype != 'POS Branch Day Closing':
        frappe.throw('POS Branch Day Closing is required.')
    doc.check_permission('read')
    # Print previews can carry edited document JSON. Source lookups must use
    # the persisted, permission-checked closing rather than supplied shift IDs.
    if not doc.is_new():
        doc = frappe.get_doc('POS Branch Day Closing', doc.name)
        doc.check_permission('read')
    shifts = [r.cashier_shift for r in doc.cashier_summaries if r.cashier_shift]
    invoices, payments = [], []
    if shifts:
        invoices = frappe.get_all('POS Invoice', filters={'pos_cashier_shift': ['in', shifts], 'docstatus': 1},
            fields=['name', 'company', 'currency', 'net_total', 'grand_total', 'discount_amount', 'total_taxes_and_charges', 'rounding_adjustment',
                    'change_amount', 'account_for_change_amount', 'is_return', 'conversion_rate', 'pos_counter', 'pos_cashier_shift'])
        names = [i.name for i in invoices]
        for dt, fields, key in [('POS Invoice Item', ['parent', 'item_code', 'item_name', 'item_group', 'net_amount'], 'items'),
                ('Sales Invoice Payment', ['parent', 'mode_of_payment', 'account', 'amount'], 'payments'),
                ('Sales Taxes and Charges', ['parent', 'account_head', 'description', 'charge_type', 'rate', 'tax_amount', 'tax_amount_after_discount_amount', 'item_wise_tax_detail'], 'taxes')]:
            grouped = defaultdict(list)
            if names:
                for row in frappe.get_all(dt, filters={'parent': ['in', names], 'parenttype': 'POS Invoice'}, fields=fields, order_by='idx asc'):
                    grouped[row.parent].append(row)
            for invoice in invoices:
                invoice[key] = grouped[invoice.name]
        payments = frappe.get_all('Payment Entry', filters={'pos_cashier_shift': ['in', shifts], 'docstatus': 1, 'payment_type': ['in', ['Receive', 'Pay']]},
            fields=['mode_of_payment', 'payment_type', 'paid_amount', 'received_amount', 'pos_counter', 'pos_cashier_shift'])
    result = aggregate(invoices, payments, doc)
    companies = {i.company for i in invoices}
    if not companies:
        companies = set(frappe.get_all('POS Branch Counter', filters={'branch': doc.branch}, pluck='company')) - {None, ''}
    result['company'] = next(iter(companies)) if len(companies) == 1 else ''
    currencies = {i.currency for i in invoices}
    result['currency'] = next(iter(currencies)) if len(currencies) == 1 else (frappe.db.get_value('Company', result['company'], 'default_currency') if result['company'] else '')
    if len(currencies) > 1:
        # Never imply that mixed-currency sums form a meaningful money total.
        result['warnings'].append('Linked invoices use multiple currencies. Detailed financial breakdowns are hidden; review the source invoices.')
        result['mixed_currency'] = True
    result['counter_names'] = {r.counter: r.counter_code or r.counter for r in doc.counter_summaries}
    result['cashier_names'] = {r.cashier_shift: r.cashier_name or r.cashier_employee or r.cashier_shift for r in doc.cashier_summaries}
    return frappe._dict(result)

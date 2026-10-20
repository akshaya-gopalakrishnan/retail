"""Read saved item tax breakups for printing; never recalculate a document."""
import json


def item_tax_for_print(doc, item):
    key = item.get('item_code') or item.get('item_name')
    siblings = [row for row in doc.get('items', []) if (row.get('item_code') or row.get('item_name')) == key]
    conversion = float(doc.get('conversion_rate') or 1)
    amount = 0.0
    rates = []
    for tax in doc.get('taxes', []):
        if tax.get('category') == 'Valuation':
            continue
        details = tax.get('item_wise_tax_detail') or {}
        if isinstance(details, str):
            details = json.loads(details)
        detail = details.get(key)
        if not isinstance(detail, (list, tuple)) or len(detail) < 2:
            continue
        def weight(row):
            value = float(row.get('net_amount') or 0)
            if tax.get('charge_type') == 'On Item Quantity':
                return float(row.get('qty') or 0)
            if tax.get('charge_type') == 'On Net Total':
                overrides = row.get('item_tax_rate') or {}
                if isinstance(overrides, str):
                    overrides = json.loads(overrides)
                return value * float(overrides.get(tax.get('account_head'), tax.get('rate') or 0))
            return value
        total_weight = sum(weight(row) for row in siblings)
        share = weight(item) / total_weight if total_weight else (1 / len(siblings) if siblings else 0)
        sign = -1 if tax.get('add_deduct_tax') == 'Deduct' else 1
        amount += sign * float(detail[1] or 0) / conversion * share
        if tax.get('charge_type') == 'On Net Total':
            overrides = item.get('item_tax_rate') or {}
            if isinstance(overrides, str):
                overrides = json.loads(overrides)
            rates.append(sign * float(overrides.get(tax.get('account_head'), detail[0] or 0)))
        elif tax.get('charge_type') in ('On Previous Row Amount', 'On Previous Row Total'):
            rates.append(sign * float(detail[0] or 0))
    return {'rate': sum(rates), 'amount': amount}

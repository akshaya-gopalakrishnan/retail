"""Render completed POS tax breakdowns from final invoice amounts, without posting."""
import frappe
from frappe.utils import flt


def update(doc):
    from retail.pos_completed_sale import payload_for
    if not payload_for(doc):
        return
    from erpnext.controllers.taxes_and_totals import get_itemised_tax_breakup_html

    display = frappe.get_doc(doc.as_dict())
    # Core's template uses absolute values for returns; retain signed receipt facts.
    display.is_return = 0
    factor = flt(display.conversion_rate) or 1
    net = {}
    vat = {}
    for item in display.items:
        key = item.item_code or item.item_name
        net[key] = net.get(key, 0) + flt(item.net_amount)
        vat[key] = vat.get(key, 0) + flt(item.get('custom_vat_amount')) * factor
    for tax in display.taxes:
        original = frappe.parse_json(tax.item_wise_tax_detail or '{}')
        weights = {key: flt(value[1]) if isinstance(value, list) else 0
                   for key, value in original.items() if key in net}
        if len(display.taxes) == 1 and all(item.get('custom_vat_amount') is not None for item in display.items):
            weights = vat
        if not sum(weights.values()):
            weights = {key: abs(value) for key, value in net.items()}
        total = sum(weights.values())
        if not total:
            weights = dict.fromkeys(net, 1)
            total = len(net)
        target = flt(tax.base_tax_amount)
        details = {}
        for key in net:
            old = original.get(key, [0, 0])
            rate = flt(old[0] if isinstance(old, list) else old)
            details[key] = [rate, target * weights.get(key, 0) / total if total else 0]
        tax.item_wise_tax_detail = frappe.as_json(details)
    doc.other_charges_calculation = get_itemised_tax_breakup_html(display)


def execute():
    """Repair derived HTML only; leave posted financial/stock facts untouched."""
    changed = 0
    for name in frappe.get_all('POS Invoice', filters={'pos_sync_source': 'Offline POS'}, pluck='name'):
        doc = frappe.get_doc('POS Invoice', name)
        old = doc.other_charges_calculation
        update(doc)
        if doc.other_charges_calculation != old:
            frappe.db.set_value('POS Invoice', name, 'other_charges_calculation',
                                doc.other_charges_calculation, update_modified=False)
            frappe.clear_document_cache('POS Invoice', name)
            changed += 1
    return {'updated_tax_breakdowns': changed}

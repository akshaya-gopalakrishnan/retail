"""Narrow, repeatable upgrade of the editable Sales Invoice A4 layout."""
import re

MARKER = 'retail-trading-vat-layout-v1'


def conditional_layout(html):
    if MARKER in html:
        return html
    # Only known A4 elements are changed; customer letterheads, CSS and terms stay owned by the site.
    html = re.sub(r'(<(th|td) class="(?:col-tax-rate|col-tax|col-rate-incl)">.*?</\2>)',
                  r'{% if not doc.get("custom_trading_vat_disabled") %}\1{% endif %}', html, flags=re.S)
    for old, plain in [('Rate Excl. VAT', 'Rate'), ('Total Incl. VAT', 'Amount'),
                       ('Subtotal (Taxable Amount)', 'Subtotal'), ('Total (Incl. VAT)', 'Total')]:
        html = html.replace('{{ _("' + old + '") }}',
            '{{ _("' + plain + '") if doc.get("custom_trading_vat_disabled") else _("' + old + '") }}')
    html = re.sub(r'(<tr>\s*<td class="totals-label">\s*{{ _\("VAT"\) }}.*?</tr>)',
                  r'{% if not doc.get("custom_trading_vat_disabled") %}\1{% endif %}', html, flags=re.S)
    # Scoped rules override only the widths of the five-column, VAT-disabled layout.
    html += '''
<!-- retail-trading-vat-layout-v1 -->
{% if doc.get("custom_trading_vat_disabled") %}
<style>
.print-format .item-table .col-number { width: 4% !important; }
.print-format .item-table .col-description { width: 49% !important; }
.print-format .item-table .col-qty { width: 15% !important; }
.print-format .item-table .col-rate { width: 15% !important; }
.print-format .item-table .col-amount { width: 17% !important; }
</style>
{% endif %}
'''
    return html


def install():
    import frappe
    if not frappe.db.exists('Print Format', 'Sales Invoice - A4'):
        return
    original = frappe.db.get_value('Print Format', 'Sales Invoice - A4', 'html') or ''
    html = print_audit_footer(reorder_taxed_columns(conditional_layout(original)))
    if html != original:
        frappe.db.set_value('Print Format', 'Sales Invoice - A4', 'html', html)
        frappe.clear_document_cache('Print Format', 'Sales Invoice - A4')


def reorder_taxed_columns(html):
    marker = 'retail-trading-vat-columns-v2'
    if marker in html:
        return html
    for tag in ('th', 'td'):
        pattern = rf'(?P<rate><{tag} class="col-rate">.*?</{tag}>)(?P<gap>\s*)(?P<taxes>{{% if not doc.get\("custom_trading_vat_disabled"\) %}}<{tag} class="col-tax-rate">.*?</{tag}>{{% endif %}}\s*{{% if not doc.get\("custom_trading_vat_disabled"\) %}}<{tag} class="col-tax">.*?</{tag}>{{% endif %}})'
        html = re.sub(pattern, r'\g<taxes>\g<gap>\g<rate>', html, flags=re.S)
        content = '{{ _("Total Excl. VAT") }}' if tag == 'th' else '{{ frappe.utils.fmt_money(item.net_amount, precision=2) }}'
        cell = '{% if not doc.get("custom_trading_vat_disabled") %}<' + tag + ' class="col-amount-excl">' + content + '</' + tag + '>{% endif %}\n'
        html = html.replace('<' + tag + ' class="col-amount">', cell + '<' + tag + ' class="col-amount">', 1)
    html += '''
<!-- retail-trading-vat-columns-v2 -->
{% if not doc.get("custom_trading_vat_disabled") %}
<style>
.print-format .item-table .col-number { width: 4% !important; }
.print-format .item-table .col-description { width: 29% !important; }
.print-format .item-table .col-qty { width: 11% !important; }
.print-format .item-table .col-tax-rate { width: 5% !important; }
.print-format .item-table .col-tax { width: 8% !important; }
.print-format .item-table .col-rate { width: 10% !important; }
.print-format .item-table .col-rate-incl { width: 10% !important; }
.print-format .item-table .col-amount-excl { width: 11% !important; text-align: right; }
.print-format .item-table .col-amount { width: 12% !important; }
</style>
{% endif %}
'''
    return html


def print_audit_footer(html):
    if 'retail-print-audit' in html:
        return html
    return html + '''
<div class="retail-print-audit" style="margin-top: 12px; font-size: 8px; line-height: 1.3; color: #666; text-align: right; break-inside: avoid;">
{{ frappe.get_fullname(frappe.session.user) | e }} &nbsp; {{ frappe.utils.format_datetime(frappe.utils.now(), "dd-MM-yyyy HH:mm:ss") }}
</div>
'''

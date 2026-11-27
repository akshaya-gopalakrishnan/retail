"""Shared Sales Invoice / Delivery Note presentation, without changing columns."""
from io import BytesIO
import re

import frappe

MARKER = 'retail-22-item-pages-v1'
GENERATOR = 'retail-numbered'
PAGINATION_CSS = '''
/* retail-22-item-pages-v1 */
.print-format .retail-item-table-continuation { page-break-before: always; break-before: page; }
.print-format .item-table thead { display: table-header-group; }
.print-format .item-table tr { page-break-inside: avoid; break-inside: avoid; }
'''
DELIVERY_CSS = '''
/* retail-delivery-invoice-design-v1: preserve every Delivery Note column */
.print-format { padding: 0 !important; font-size: 12px; }
.print-format .hardcoded-letterhead { margin-bottom: 4px; }
.print-format .retail-title-table { margin: 4px 0 7px; }
.print-format .retail-title-table .document-title { font-size: 18px; }
.print-format .information-table { margin-bottom: 8px; }
.print-format .customer-section { padding-top: 0 !important; padding-right: 10px !important; }
.print-format .delivery-details td { padding: 2px 5px !important; height: auto; font-size: 12px; }
.print-format .customer-name { font-size: 12px; }
.print-format .item-table { margin-bottom: 8px; }
.print-format .item-table th { padding: 4px 3px !important; font-size: 11px; line-height: 1.2; }
.print-format .item-table td { padding: 2px 3px !important; font-size: 11px; line-height: 1.2; }
.print-format .item-table thead th { text-align: center; }
.print-format .item-table .col-description { text-align: left; }
.print-format .item-table tbody td.col-number,
.print-format .item-table tbody td.col-qty { text-align: center; }
.print-format .item-name { margin: 0; overflow-wrap: break-word; font-size: 11px; }
.print-format .retail-item-barcode, .print-format .quantity-uom { font-size: 10px; }
.print-format .item-table tbody tr:nth-child(odd) > td { background: #f0f3f7 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.print-format .item-table tbody tr:nth-child(even) > td { background: #fff !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
'''

DELIVERY_COMPACT_CSS = """
/* retail-delivery-invoice-compact-v2 */
.print-format .retail-title-rule { display: none; }
.print-format .retail-title-cell { width: 100%; text-align: center; }
.print-format .item-name { display: inline; }
.print-format .item-code { display: inline; margin-left: 6px; font-size: 9px; }
.print-format .item-description { margin: 0; font-size: 10px; line-height: 1.15; }
.print-format .item-image { width: 28px; height: 28px; max-width: 28px; max-height: 28px; }
.print-format .signature-section { margin-top: 24px; }
.print-format .signature-field { margin-bottom: 20px; }
.print-format .stamp-label { margin-top: 35px; }
"""


DELIVERY_TABLE_CSS = """
/* retail-delivery-invoice-table-v3 */
.print-format .item-table { border: 1px solid #111; }
.print-format .item-table th { background: transparent !important; color: #000 !important; border: 1px solid #111 !important; }
.print-format .item-table th * { background: transparent !important; color: #000 !important; }
.print-format .item-table td { border: none !important; }
.print-format .item-name { font-weight: 500; }
"""


def delivery_footer(html, css):
    marker = 'retail-delivery-footer-v6'
    if marker not in html:
        signature = re.search(r'<div class="signature-section">.*?</table>\s*</div>', html, re.S)
        if signature and 'id="footer-html"' not in html:
            block = signature[0]
            html = html[:signature.start()] + html[signature.end():]
            letterhead = re.search(r'{% if footer and not no_letterhead %}.*?{% endif %}', html, re.S)
            footer = letterhead[0] if letterhead else ''
            if letterhead:
                html = html[:letterhead.start()] + html[letterhead.end():]
            html += '\n<!-- ' + marker + ' -->\n<div id="footer-html" class="retail-delivery-footer">' + block + footer + '</div>\n'
    if marker in html and marker not in css:
        css += """
/* retail-delivery-footer-v6 */
.print-format #footer-html.retail-delivery-footer .signature-section { margin-top: 0; }
.print-format #footer-html.retail-delivery-footer .signature-table { margin: 0; }
@supports (display: grid) {
    @media print {
        .print-format #footer-html.retail-delivery-footer { position: fixed; bottom: 0; left: 0; width: 100%; }
    }
}
"""
    return html, css


def delivery_design(html, css):
    html = re.sub(r'{%\s*if item.item_code\s*%}\s*<div class="item-code">.*?</div>\s*{%\s*endif\s*%}', '', html, flags=re.S)
    html = re.sub(r'<div class="(quantity-value|quantity-uom)">(.*?)</div>',
                  r'<span class="\1">\2</span>', html, flags=re.S)
    if 'retail-delivery-inline-qty-v5' not in css:
        css += """
/* retail-delivery-inline-qty-v5 */
.print-format .item-table .col-qty { white-space: nowrap; }
.print-format .quantity-value, .print-format .quantity-uom { display: inline; margin: 0; }
.print-format .quantity-uom { margin-left: 3px; }
"""
    # Do not print the same name again as a separate description line.
    html = html.replace('{% if item.description %}',
        '{% if item.description and (item.description | striptags | trim) != (item.item_name | trim) %}')
    if 'retail-delivery-invoice-design-v1' not in css:
        css += '\n' + DELIVERY_CSS
    if 'retail-delivery-invoice-compact-v2' not in css:
        css += '\n' + DELIVERY_COMPACT_CSS
    if 'retail-delivery-invoice-table-v3' not in css:
        css += '\n' + DELIVERY_TABLE_CSS
    return html, css


NEUTRAL_HEADER_CSS = """
/* retail-neutral-print-header-v4 */
.print-format table thead th,
.print-format .item-table th,
.print-format .item-table th * { background: #fff !important; color: #000 !important; }
"""
DELIVERY_COLUMNS_CSS = """
/* retail-delivery-name-first-v4 */
.print-format .item-table .col-number { width: 6%; }
.print-format .item-table .col-description { width: 79%; }
.print-format .item-table .col-qty { width: 15%; }
"""


def document_header(html, css, doctype):
    if doctype == 'Delivery Note':
        html = re.sub(r'<th class="col-image">.*?</th>\s*', '', html, flags=re.S)
        html = re.sub(r'<td class="col-image">.*?</td>\s*', '', html, flags=re.S)
        html = re.sub(r'{% set master_item_image = .*?%}\s*', '', html, flags=re.S)
        html = re.sub(r'{% set display_image = .*?%}\s*', '', html, flags=re.S)
        html = re.sub(r'<th class="col-number">.*?</th>', '<th class="col-number">{{ _("Sr No") }}</th>', html, flags=re.S)
        html = re.sub(r'<th class="col-description">.*?</th>', '<th class="col-description">{{ _("Item Name") }}</th>', html, flags=re.S)
        if 'retail-delivery-name-first-v4' not in css:
            css += '\n' + DELIVERY_COLUMNS_CSS
    html = re.sub(r'<th class="col-number">.*?</th>', '<th class="col-number">{{ _("Sr No") }}</th>', html, flags=re.S)
    html = re.sub(r'<th class="col-description">.*?</th>', '<th class="col-description">{{ _("Item Name") }}</th>', html, flags=re.S)
    if 'retail-neutral-print-header-v4' not in css:
        css += '\n' + NEUTRAL_HEADER_CSS
    return html, css


def paginate_items(html, css):
    if MARKER in html:
        return html, css
    table = re.search(r'<table\b[^>]*class="item-table"[^>]*>\s*(<thead>.*?</thead>)\s*<tbody>\s*{%\s*for item in doc.items\s*%}', html, re.S)
    if not table:
        raise ValueError('Expected an item-table with the editable document item loop')
    start = table.end()
    end = html.index('{% endfor %}', start)
    footer = re.search(r'<tfoot class="retail-browser-footer-space".*?</tfoot>', html[end:], re.S)
    spacer = footer[0] if footer else ''
    continuation = ('\n{% if loop.index % 22 == 0 and not loop.last %}\n'
                    '</tbody>' + spacer + '</table>\n'
                    '<table class="item-table retail-item-table-continuation">' + table[1] + '<tbody>\n'
                    '{% endif %}\n')
    html = html[:end] + continuation + html[end:]
    html += '\n<!-- ' + MARKER + ' -->\n'
    return html, (css or '') + '\n' + PAGINATION_CSS


def invoice_last_page_summary(html, css):
    """Keep invoice totals and terms in document flow, outside PDF page footers."""
    html = html.replace('id="footer-html" class="retail-invoice-footer"',
                        'class="retail-invoice-summary"')
    html = re.sub(r'<tfoot class="retail-browser-footer-space".*?</tfoot>', '', html, flags=re.S)
    css = re.sub(r'/\* Chromium browser printing needs.*?(?=/\* retail-22-item-pages-v1 \*/)', '', css, flags=re.S)
    marker = 'retail-invoice-last-page-summary-v1'
    if marker not in css:
        css += """
/* retail-invoice-last-page-summary-v1 */
.print-format .retail-invoice-summary {
    position: static;
    width: 100%;
    page-break-inside: avoid;
    break-inside: avoid;
}
"""
    return html, css


def numbered_pdf(data, password=None):
    """Use physical PDF page count, including overflow from long descriptions."""
    from pypdf import PdfReader, PdfWriter, PageObject
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt(password or '')
    total = len(reader.pages)
    if total <= 1:
        return data
    writer = PdfWriter()
    for number, page in enumerate(reader.pages, 1):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        overlay = PageObject.create_blank_page(width=width, height=height)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        overlay[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/RetailPageFont'): font})})
        label = f'Page {number} of {total}'
        stream = DecodedStreamObject()
        # Reserve the bottom page margin; business footer content stays above it.
        stream.set_data(f'q 0.35 g BT /RetailPageFont 8 Tf 1 0 0 1 {width / 2 - len(label) * 2:.2f} 16 Tm ({label}) Tj ET Q'.encode('ascii'))
        overlay[NameObject('/Contents')] = stream
        target = writer.add_page(page)
        target.merge_page(overlay)
    if reader.metadata:
        writer.add_metadata({key: str(value) for key, value in reader.metadata.items() if value is not None})
    if password:
        writer.encrypt(password)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def generate_pdf(print_format=None, html=None, options=None, output=None, pdf_generator=None):
    if pdf_generator != GENERATOR:
        return None
    from frappe.utils.pdf import get_pdf
    data = get_pdf(html, options=options)
    return numbered_pdf(data, password=(options or {}).get('password'))


def install():
    """Upgrade only the requested A4 formats; keep saved HTML and column cells."""
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    field = frappe.get_meta('Print Format').get_field('pdf_generator')
    if not field:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
        create_custom_fields({'Print Format': [dict(fieldname='pdf_generator', label='PDF Generator',
            fieldtype='Select', options='wkhtmltopdf', default='wkhtmltopdf', insert_after='print_format_type')]})
        field = frappe.get_meta('Print Format').get_field('pdf_generator')
    choices = (field.options or '').splitlines()
    if GENERATOR not in choices:
        make_property_setter('Print Format', 'pdf_generator', 'options', '\n'.join([*choices, GENERATOR]), 'Text')
    for doctype in ('Sales Invoice', 'Delivery Note'):
        name = doctype + ' - A4'
        if not frappe.db.exists('Print Format', name):
            continue
        doc = frappe.get_doc('Print Format', name)
        try:
            html, css = paginate_items(doc.html or '', doc.css or '')
        except ValueError:
            frappe.logger('retail').warning('Kept customized print format %s: item layout is not recognized', name)
            continue
        if doctype == 'Delivery Note':
            html, css = delivery_design(html, css)
            html, css = delivery_footer(html, css)
        if doctype == 'Sales Invoice':
            html, css = invoice_last_page_summary(html, css)
        html, css = document_header(html, css, doctype)
        if (html, css, doc.pdf_generator) != (doc.html, doc.css, GENERATOR):
            doc.html, doc.css, doc.pdf_generator = html, css, GENERATOR
            doc.save(ignore_permissions=True)
            frappe.clear_document_cache('Print Format', name)

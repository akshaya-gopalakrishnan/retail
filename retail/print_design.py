"""Portable print-header design; site copies remain independently editable."""
import re

HEADER_CSS = '''/* Compact letterhead and centred document title */
.print-format .retail-letterhead { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 12px; }
.print-format .retail-letterhead td { border: none !important; padding: 0 !important; vertical-align: bottom; }
.print-format .retail-letterhead .retail-logo { width: 50%; text-align: left; }
.print-format .retail-letterhead .retail-company { width: 50%; text-align: right; }
.print-format .retail-letterhead .retail-logo img { width: 250px !important; max-width: 100% !important; height: auto !important; max-height: 85px; object-fit: contain; }
.print-format .retail-letterhead .retail-company img { width: 210px !important; max-width: 100% !important; height: auto !important; max-height: 115px; object-fit: contain; }
.print-format .retail-title-table { width: 100%; border-collapse: collapse; table-layout: auto; margin: 12px 0 4px; }
.print-format .retail-title-table td { border: none !important; padding: 0 !important; vertical-align: middle; }
.print-format .retail-title-rule { width: 50%; }
.print-format .retail-title-rule div { border-top: 1px solid #333; }
.print-format .retail-title-table .retail-title-cell { padding: 0 18px !important; width: auto; white-space: nowrap; text-align: center; }
.print-format .retail-title-table .document-title { font-size: 18px; font-weight: normal; line-height: 1.3; color: #2d6dc4; text-transform: uppercase; margin: 0; }
.print-format .retail-document-number { text-align: right; font-size: 10px; margin: 4px 0 12px; }
.print-format .title-row { margin: 12px 0; }
.print-format .invoice-title { color: #2d6dc4; font-size: 18px; font-weight: normal; text-transform: uppercase; }
'''


def compact_header(html, css):
    pattern = r'<table class="document-heading-table">.*?</table>'
    def replace(match):
        title = re.search(r'<h1 class="document-title">(.*?)</h1>', match[0], re.S)
        number = re.search(r'<div class="document-number">(.*?)</div>', match[0], re.S)
        if not title:
            return match[0]
        return '''<table class="retail-title-table"><tr>
            <td class="retail-title-rule"><div></div></td>
            <td class="retail-title-cell"><h1 class="document-title">''' + title[1].strip() + '''</h1></td>
            <td class="retail-title-rule"><div></div></td>
        </tr></table>
        <div class="retail-document-number">''' + (number[1].strip() if number else '') + '</div>'
    html = re.sub(pattern, replace, html, flags=re.S)
    if '/* Compact letterhead and centred document title */' not in (css or ''):
        css = (css or '') + '\n' + HEADER_CSS
    return html, css

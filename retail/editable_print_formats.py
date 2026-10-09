"""Install user-owned print formats once; never overwrite their HTML on migrate."""

import html
import json
import re
from pathlib import Path

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


SOURCES = {
    "Sales Invoice": "Sales Invoice - Copy",
    "Delivery Note": "Delivery Note- Copy",
    "Quotation": "Sales Quotation",
    **{dt: f"{dt} - Retail" for dt in (
        "Sales Order", "Supplier Quotation", "Purchase Order", "Purchase Receipt",
        "Purchase Invoice", "Material Request",
    )},
}


def editable_html(source):
    """Inline our shared layout and use the print renderer's letterhead context."""
    include = r'''\{%\s*include\s+["']retail/templates/print_formats/retail_transaction_print.html["']\s*%\}'''
    if re.search(include, source):
        template = Path(frappe.get_app_path("retail", "templates", "print_formats", "retail_transaction_print.html"))
        source = re.sub(include, lambda _: template.read_text(), source)
    # The shipped quotation's fallback bank account belongs to the original site.
    # Keep document-provided notes; a new site's UI editor can supply its own text.
    source = re.sub(
        r'(\{%\s*if doc.custom_customer_notes\s*%\}.*?)(\{%\s*else\s*%\}.*?)(\{%\s*endif\s*%\})',
        lambda m: m[1] + m[3] if "Arab Scale Trading LLC" in m[2] else m[0],
        source,
        flags=re.S,
    )
    source = re.sub(
        r'''\{%\s*set\s+fixed_(letterhead|footer)\s*=\s*frappe.db.get_value\(\s*"Letter Head",\s*"Arab Scale Letter Head - Standard",\s*"(?:content|footer)"\s*\)\s*%\}''',
        lambda m: "{% set fixed_" + m[1] + " = " + ("letter_head" if m[1] == "letterhead" else "footer") + " if not no_letterhead else '' %}",
        source,
    )
    # Stored document text needs an explicit translation lookup at print time.
    for expression, replacement in {
        "item.item_name or item.item_code": "_(item.item_name) if item.item_name else item.item_code",
        "item.description": "_(item.description)",
        "item.uom": "_(item.uom)",
        "item.uom or item.stock_uom": "_(item.uom or item.stock_uom)",
    }.items():
        source = re.sub(r"\{\{\s*" + re.escape(expression) + r"\s*\}\}", "{{ " + replacement + " }}", source)
    source = re.sub(
        r"\{\{\s*doc.in_words(?:\s+or\s+[\"']{2})?\s*\}\}",
        "{{ frappe.utils.money_in_words((doc.rounded_total if doc.get('rounded_total') is not none and not doc.is_rounded_total_disabled() else doc.grand_total)|abs, doc.currency) }}",
        source,
    )
    # Keep Jinja and HTML attributes untouched; translate text even beside a value.
    tokens = re.split(r"(<!--.*?-->|<style\b.*?</style>|<script\b.*?</script>|\{%.*?%\}|\{\{.*?\}\}|<[^>]+>)", source, flags=re.S | re.I)
    aliases = {
        "DELIVERY NOTE": "Delivery Note", "TAX INVOICE": "Tax Invoice",
        "CREDIT NOTE": "Credit Note", "Sub Total": "Subtotal",
        "Items in Total": "Total Quantity", "Item & Description": "Item Description",
        "Total In Words": "In Words", "Amount in words": "In Words",
        "Bill to": "Bill To", "Sales person": "Sales Person",
        "Rate in": "Rate", "S.No": "Sr No", "S": "Sr", "N": "No",
        "Mob/Tel No": "Phone", "Receiver's Name": "Receiver Name",
        "Serial Number": "Serial No", "P.O.": "Purchase Order",
        "Customer P.O.": "Customer Purchase Order", "TRN": "Tax ID",
    }
    for i in range(0, len(tokens), 2):
        value = tokens[i]
        label = " ".join(html.unescape(value).split())
        if not re.search(r"[A-Za-z]", label) or "{" in label or "}" in label:
            continue
        match = re.fullmatch(r"(.*?)([ :#%(]+)?", label)
        key, suffix = match[1], match[2] or ""
        key = aliases.get(key, key)
        tokens[i] = value[:len(value)-len(value.lstrip())] + "{{ _(" + json.dumps(key) + ") }}" + suffix + value[len(value.rstrip()):]
    source = "".join(tokens)
    def normalize_translation(match):
        label = json.loads(match[1])
        parts = re.fullmatch(r"(.*?)([ :#%(]+)?", " ".join(label.split()))
        key = aliases.get(parts[1], parts[1])
        return "{{ _(" + json.dumps(key) + ") }}" + (parts[2] or "")
    source = re.sub(r'\{\{\s*_\(("(?:[^"\\]|\\.)*")\)\s*\}\}', normalize_translation, source)
    source = source.replace("{{ doc_title }}", "{{ _(doc_title.title()) }}")
    source = source.replace('else party_label }}', 'else _(party_label) }}').replace('"Requested For" if', '_("Requested For") if')
    if "fixed_footer" not in source and "letter-head-footer" not in source:
        source += '\n{% if footer and not no_letterhead %}<div class="letter-head-footer">{{ footer }}</div>{% endif %}\n'
    if "retail-print-language-layout" not in source:
        source += '\n<style id="retail-print-language-layout">\n[dir="rtl"] .print-format { text-align: right; }\n[dir="rtl"] .print-format .heading-section, [dir="rtl"] .print-format .document-info-section { text-align: left; }\n[dir="rtl"] .print-format .col-description { text-align: right; }\n</style>\n'
    return source


def ensure_editable_print_formats():
    if not frappe.db.table_exists("Print Format"):
        return
    for doctype, source_name in SOURCES.items():
        if not frappe.db.exists("Print Format", source_name):
            continue
        name = f"{doctype} - A4"
        previous_name = f"{doctype} - Editable"
        if frappe.db.exists("Print Format", previous_name) and not frappe.db.exists("Print Format", name):
            frappe.rename_doc("Print Format", previous_name, name, force=True)

        if not frappe.db.exists("Print Format", name):
            source = frappe.get_doc("Print Format", source_name)
            target = frappe.copy_doc(source)
            target.name = name
            target.standard = "No"
            target.custom_format = 1
            target.print_format_builder = 0
            target.print_format_builder_beta = 0
            target.print_format_for = "DocType"
            target.html = editable_html(source.html or "")
            target.insert(ignore_permissions=True)
        # Upgrade translation expressions in place, preserving user-written layout.
        existing = frappe.get_doc("Print Format", name)
        updated_html = editable_html(existing.html or "")
        if updated_html != existing.html:
            existing.html = updated_html
            existing.save(ignore_permissions=True)
        legacy = frappe.get_doc("Print Format", source_name)
        legacy_html = editable_html(legacy.html or "")
        if legacy_html != legacy.html:
            frappe.db.set_value("Print Format", source_name, "html", legacy_html)
        current = frappe.get_meta(doctype).default_print_format
        if current and current not in (source_name, name, previous_name, "Standard"):
            continue
        if current != name:
            make_property_setter(doctype, None, "default_print_format", name, "Data", for_doctype=True)
        frappe.clear_cache(doctype=doctype)

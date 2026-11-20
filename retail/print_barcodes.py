"""Barcode display for item print rows; never changes transaction records."""
import re

import frappe


def item_barcode_for_print(row):
	# Historical/scanned values take precedence over today's Item master.
	for field in ("barcode", "custom_item_barcode"):
		if row.get(field):
			return row.get(field)
	code = row.get("item_code") or row.get("item")
	if not code:
		return ""
	cache = getattr(frappe.local, "retail_print_barcodes", None)
	if cache is None:
		cache = frappe.local.retail_print_barcodes = {}
	key = (code, row.get("uom"), row.get("custom_packing_detail"))
	if key not in cache:
		item = frappe.db.get_value("Item", code, ["stock_uom", "custom_barcode"], as_dict=True)
		value = ""
		if item:
			packing = row.get("custom_packing_detail")
			if packing:
				value = frappe.db.get_value("Retail Packing Detail", {"name": packing, "parent": code, "parenttype": "Item"}, "barcode") or ""
			elif row.get("uom") and row.get("uom") != item.stock_uom:
				choices = frappe.get_all("Retail Packing Detail", filters={"parent": code, "parenttype": "Item", "uom": row.get("uom")}, fields=["barcode"], limit_page_length=2)
				if len(choices) == 1:
					value = choices[0].barcode or ""
			else:
				value = item.custom_barcode or frappe.db.get_value("Item Barcode", {"parent": code, "parenttype": "Item"}, "barcode") or ""
		cache[key] = value
	return cache[key]


def add_barcode_lines(source):
	"""Add beside visible item names, leaving image attributes and layout intact."""
	if 'retail-item-barcode' in source or 'item_barcode_for_print(' in source:
		return source
	# Split complete Jinja expressions first, so HTML comparisons inside them survive.
	tokens = re.split(r'(<[^>]+>)', source)
	pattern = r'\{\{(?P<expr>[^{}]*(?:\b(?P<row>\w+)\.item_name|frappe\.db\.get_value\("Item",\s*\b(?P<promo>\w+)\.item,\s*"item_name")[^{}]*)\}\}'
	def append(match):
		row = match['row'] or match['promo']
		if row == 'doc':
			return match[0]  # Item labels already print their barcode.
		return match[0] + ('{% set retail_barcode = item_barcode_for_print(' + row + ') %}'
			'{% if retail_barcode %}<br><small class="retail-item-barcode" style="font-weight: normal; overflow-wrap: anywhere;">{{ _("Barcode") }}: {{ retail_barcode | e }}</small>{% endif %}')
	for index in range(0, len(tokens), 2):
		tokens[index] = re.sub(pattern, append, tokens[index])
	return ''.join(tokens)


def install():
	"""Narrow, repeatable update of existing site-owned item print layouts."""
	updated = []
	for layout in frappe.get_all("Print Format", fields=["name", "html", "print_format_type"]):
		if layout.print_format_type != "Jinja":
			continue
		source = layout.html or ""
		result = add_barcode_lines(source)
		if result != source:
			frappe.db.set_value("Print Format", layout.name, "html", result)
			frappe.clear_document_cache("Print Format", layout.name)
			updated.append(layout.name)
	return updated


def install_report_lines():
	"""Extend the shared report cell without replacing site-owned report layouts."""
	from pathlib import Path
	from retail.report_print_formats import POS_PRINT_REPORTS

	packaged = (Path(__file__).parent / "templates/report_print_formats/pos_report.html").read_text()
	start = packaged.index('{% if (col === barcodeColumn')
	end = packaged.index('</td>', start)
	addition = packaged[start:end]
	for report in POS_PRINT_REPORTS:
		name = f"{report} - A4"
		source = frappe.db.get_value("Print Format", name, "html") or ""
		anchor = '{% } else { %}{%= escape(raw) %}{% } %}</td>'
		if 'retail-item-barcode' in source or anchor not in source:
			continue
		source = source.replace(' const bands = [];', ' const barcodeColumn = selected.find(col => ["item_code", "item_name"].includes(col.fieldname));\n const bands = [];')
		source = source.replace(anchor, anchor[:-5] + '\n' + addition + '</td>')
		frappe.db.set_value("Print Format", name, "html", source)
		frappe.clear_document_cache("Print Format", name)

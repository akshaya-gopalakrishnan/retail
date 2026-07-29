import html
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")


class ZebraLabelFormat(Document):
	def validate(self):
		if self.is_default and self.enabled:
			clear_other_defaults(self.name, self.label_type)


def clear_other_defaults(name, label_type):
	frappe.db.set_value(
		"Zebra Label Format",
		{"name": ["!=", name], "label_type": label_type, "is_default": 1},
		"is_default",
		0,
		update_modified=False,
	)


@frappe.whitelist()
def set_default(label_format):
	doc = frappe.get_doc("Zebra Label Format", label_format)
	doc.check_permission("write")
	doc.enabled = 1
	doc.is_default = 1
	doc.save()
	return doc.name


@frappe.whitelist()
def render_label(label_format, item=None, copies=None, price=None, currency=None):
	label = frappe.get_doc("Zebra Label Format", label_format)
	label.check_permission("read")
	item_doc = get_item_doc(item or label.sample_item)
	context = get_label_context(label, item_doc, copies=copies, price=price, currency=currency)
	zpl = render_zpl(label.zpl_template or "", context)
	return {
		"zpl": zpl,
		"context": context,
		"preview_html": build_preview_html(label, context),
	}


@frappe.whitelist()
def print_label(label_format, item=None, copies=None, price=None, currency=None):
	label = frappe.get_doc("Zebra Label Format", label_format)
	label.check_permission("read")

	rendered = render_label(label_format, item=item, copies=copies, price=price, currency=currency)
	return send_label_to_configured_printer(label, rendered["zpl"])


@frappe.whitelist()
def get_print_candidates(source="item_list", selected_items=None, filters=None, limit=1000):
	items = get_candidate_items(source, selected_items=selected_items, filters=filters, limit=limit)
	return {
		"count": len(items),
		"items": items[:50],
		"has_more": len(items) > 50,
	}


@frappe.whitelist()
def render_print_sample(label_format, source="item_list", selected_items=None, filters=None, copies=None, currency=None):
	items = get_candidate_items(source, selected_items=selected_items, filters=filters, limit=1)
	if not items:
		frappe.throw(_("No items found for Zebra label printing."))
	label = frappe.get_doc("Zebra Label Format", label_format)
	label.check_permission("read")
	item_doc = frappe.get_doc("Item", items[0]["item_code"])
	context = get_label_context(label, item_doc, copies=copies, currency=currency, candidate=items[0])
	zpl = render_zpl(label.zpl_template or "", context)
	return {
		"zpl": zpl,
		"context": context,
		"preview_html": build_preview_html(label, context),
	}


@frappe.whitelist()
def print_labels(label_format, source="item_list", selected_items=None, filters=None, copies=None, currency=None, limit=1000):
	label = frappe.get_doc("Zebra Label Format", label_format)
	label.check_permission("read")

	items = get_candidate_items(source, selected_items=selected_items, filters=filters, limit=limit)
	if not items:
		frappe.throw(_("No items found for Zebra label printing."))

	zpl_parts = []
	for item in items:
		item_doc = frappe.get_doc("Item", item["item_code"])
		context = get_label_context(label, item_doc, copies=copies, currency=currency, candidate=item)
		zpl_parts.append(render_zpl(label.zpl_template or "", context))

	return send_label_to_configured_printer(label, "\n".join(zpl_parts), label_count=len(items))


@frappe.whitelist()
def get_default_format(label_type=None):
	filters = {"enabled": 1, "is_default": 1}
	if label_type:
		filters["label_type"] = label_type
	name = frappe.db.get_value("Zebra Label Format", filters, "name", order_by="modified desc")
	if not name:
		filters.pop("is_default", None)
		name = frappe.db.get_value("Zebra Label Format", filters, "name", order_by="modified desc")
	return name


@frappe.whitelist()
def get_system_printers():
	if os.name == "nt":
		return get_windows_system_printers()
	return get_cups_system_printers()


def get_cups_system_printers():
	command = ["lpstat", "-a"]
	if not shutil.which("lpstat"):
		return []
	try:
		result = subprocess.run(command, check=True, capture_output=True, text=True)
	except subprocess.CalledProcessError:
		return []
	return [line.split()[0] for line in result.stdout.splitlines() if line.strip()]


def get_windows_system_printers():
	if not shutil.which("powershell"):
		return []
	command = ["powershell", "-NoProfile", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"]
	try:
		result = subprocess.run(command, check=True, capture_output=True, text=True)
	except subprocess.CalledProcessError:
		return []
	return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_candidate_items(source="item_list", selected_items=None, filters=None, limit=1000):
	selected_items = parse_json_value(selected_items, [])
	filters = parse_json_value(filters, {})
	limit = cint(limit) or 1000

	if selected_items:
		return get_selected_items(selected_items, limit)
	if source == "item_family_list":
		return get_item_family_report_items(filters, limit)
	return get_item_list_filter_items(filters, limit)


def parse_json_value(value, fallback):
	if value in (None, ""):
		return fallback
	if isinstance(value, str):
		try:
			return json.loads(value)
		except ValueError:
			return fallback
	return value


def get_selected_items(selected_items, limit):
	selections = []
	seen = set()
	for item in selected_items:
		selection = normalize_selected_item(item)
		key = get_selection_key(selection)
		if selection.item_code and key not in seen:
			seen.add(key)
			selections.append(selection)
		if len(selections) >= limit:
			break

	if not selections:
		return []

	item_names = list({selection.item_code for selection in selections})
	rows = frappe.get_all(
		"Item",
		filters={"name": ["in", item_names]},
		fields=["name as item_code", "item_name", "item_group", "brand"],
		limit_page_length=limit,
		order_by="item_name asc",
	)
	row_map = {row.item_code: row for row in rows}
	items = []
	for selection in selections:
		if selection.item_code not in row_map:
			continue
		row = frappe._dict(row_map[selection.item_code])
		if selection.row_type == "packing":
			row.update(get_packing_selection_details(selection))
		else:
			row.row_type = "item"
		items.append(row)
	return items


def normalize_selected_item(item):
	if isinstance(item, dict):
		return frappe._dict(
			item_code=item.get("item_code"),
			row_type=item.get("row_type") or "item",
			packing_idx=cint(item.get("packing_idx")),
			uom=item.get("uom"),
			barcode=item.get("barcode"),
		)
	return frappe._dict(item_code=item, row_type="item", packing_idx=0, uom=None, barcode=None)


def get_selection_key(selection):
	return "::".join(
		str(part or "")
		for part in [selection.item_code, selection.row_type or "item", selection.packing_idx, selection.barcode]
	)


def get_packing_selection_details(selection):
	filters = {
		"parent": selection.item_code,
		"parenttype": "Item",
		"parentfield": "custom_retail_packing_detail",
	}
	if selection.packing_idx:
		filters["idx"] = selection.packing_idx
	elif selection.barcode:
		filters["barcode"] = selection.barcode
	elif selection.uom:
		filters["uom"] = selection.uom
	else:
		frappe.throw(_("Could not identify packing row for item {0}.").format(selection.item_code))

	packing = frappe.db.get_value(
		"Retail Packing Detail",
		filters,
		[
			"idx",
			"barcode",
			"uom",
			"conversion_factor",
			"purchase_rate",
			"selling_rate",
			"purchase_net_rate",
			"purchase_vat_amount",
			"purchase_gross_rate",
			"selling_net_rate",
			"selling_vat_amount",
			"selling_gross_rate",
			"packing_margin",
		],
		as_dict=True,
	)
	if not packing:
		frappe.throw(_("Could not find packing row for item {0}.").format(selection.item_code))

	return frappe._dict(
		row_type="packing",
		packing_idx=packing.idx,
		barcode=packing.barcode,
		uom=packing.uom,
		conversion_factor=flt(packing.conversion_factor),
		purchase_rate=flt(packing.purchase_rate),
		selling_rate=flt(packing.selling_rate),
		purchase_net_rate=flt(packing.purchase_net_rate or packing.purchase_rate),
		purchase_vat_amount=flt(packing.purchase_vat_amount),
		purchase_gross_rate=flt(packing.purchase_gross_rate or packing.purchase_rate),
		selling_net_rate=flt(packing.selling_net_rate or packing.selling_rate),
		selling_vat_amount=flt(packing.selling_vat_amount),
		selling_gross_rate=flt(packing.selling_gross_rate or packing.selling_rate),
		packing_margin=flt(packing.packing_margin),
	)


def get_item_list_filter_items(filters, limit):
	normalized_filters = normalize_item_list_filters(filters)
	return frappe.get_all(
		"Item",
		filters=normalized_filters,
		fields=["name as item_code", "item_name", "item_group", "brand"],
		limit_page_length=limit,
		order_by="item_name asc",
	)


def normalize_item_list_filters(filters):
	if not isinstance(filters, list):
		return []

	normalized = []
	for row in filters:
		if not isinstance(row, (list, tuple)) or len(row) < 4:
			continue
		doctype, fieldname, operator, value = row[:4]
		if doctype != "Item" or fieldname in {"_liked_by", "_assign", "_comments"}:
			continue
		normalized.append([doctype, fieldname, operator, value])
	return normalized


def get_item_family_report_items(filters, limit):
	from retail.retail_app.report.item_family_list.item_family_list import get_data

	rows = get_data(frappe._dict(filters if isinstance(filters, dict) else {}))
	items = []
	seen = set()
	for row in rows:
		item_code = row.get("item_code")
		if item_code and item_code not in seen:
			seen.add(item_code)
			items.append(
				frappe._dict(
					item_code=item_code,
					item_name=row.get("item_name"),
					item_group=row.get("item_group"),
					brand=row.get("brand"),
				)
			)
		if len(items) >= limit:
			break
	return items


def get_item_doc(item):
	if not item:
		frappe.throw(_("Please select a Sample Item."))
	return frappe.get_doc("Item", item)


def get_label_context(label, item_doc, copies=None, price=None, currency=None, candidate=None):
	candidate = frappe._dict(candidate or {})
	barcode = candidate.get("barcode") or get_barcode(item_doc)
	item_price = flt(price) if price not in (None, "") else get_item_price(item_doc, candidate)
	curr = currency or label.currency or get_price_currency(item_doc) or "AED"
	copies = cint(copies or label.default_copies or 1) or 1
	item_name = item_doc.item_name or item_doc.item_code or ""
	return {
		"productnameenglish": item_name,
		"productnameenglish1": item_name[28:56],
		"item_code": item_doc.item_code or item_doc.name,
		"uom": candidate.get("uom") or item_doc.stock_uom or "",
		"conversion_factor": flt(candidate.get("conversion_factor") or 1),
		"row_type": candidate.get("row_type") or "item",
		"barcode": barcode,
		"barcodetext": barcode,
		"curr": curr,
		"currency": curr,
		"price": f"{item_price:.2f}",
		"copies": copies,
	}


def get_barcode(item_doc):
	if item_doc.get("custom_barcode"):
		return item_doc.custom_barcode
	for row in item_doc.get("barcodes") or []:
		if row.get("barcode"):
			return row.barcode
	return item_doc.item_code or item_doc.name


def get_item_price(item_doc, candidate=None):
	candidate = frappe._dict(candidate or {})
	if candidate.get("row_type") == "packing":
		for fieldname in ("selling_gross_rate", "selling_rate", "selling_net_rate"):
			if candidate.get(fieldname) not in (None, ""):
				return flt(candidate.get(fieldname))

	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
	rate = frappe.db.get_value(
		"Item Price",
		{"item_code": item_doc.name, "price_list": price_list, "selling": 1},
		"price_list_rate",
	)
	return flt(rate or item_doc.get("standard_rate") or 0)


def get_price_currency(item_doc):
	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
	return frappe.db.get_value("Price List", price_list, "currency")


def render_zpl(template, context):
	def replace(match):
		key = match.group(1)
		return str(context.get(key, match.group(0)))

	return PLACEHOLDER_PATTERN.sub(replace, template)


def build_preview_html(label, context):
	width = max(cint(label.width_dots) or 305, 160)
	height = max(cint(label.height_dots) or 200, 120)
	scale = min(1.8, 520 / width)
	style = (
		f"width:{width * scale:.0f}px;height:{height * scale:.0f}px;"
		"background:#fff;border:1px solid #cbd5e1;box-shadow:0 8px 20px rgba(15,23,42,.08);"
		"position:relative;font-family:Arial,sans-serif;color:#111;overflow:hidden;"
	)
	price = html.escape(f"{context.get('curr', '')} {context.get('price', '')}")
	name = html.escape(str(context.get("productnameenglish", "")))
	name2 = html.escape(str(context.get("productnameenglish1", "")))
	barcode = html.escape(str(context.get("barcode", "")))
	if label.label_type == "Shelf Label":
		label_body = f"""
			<div style="{style}">
				<div style="position:absolute;left:16px;top:70px;font-size:18px;max-width:60%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</div>
				<div style="position:absolute;left:16px;top:112px;font-size:18px;max-width:60%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name2}</div>
				<div style="position:absolute;left:16px;top:160px;width:240px;height:70px;background:repeating-linear-gradient(90deg,#111 0 2px,#fff 2px 4px,#111 4px 5px,#fff 5px 8px);"></div>
				<div style="position:absolute;left:64px;top:245px;font-size:18px;letter-spacing:1px;">{barcode}</div>
				<div style="position:absolute;right:92px;top:150px;font-size:28px;font-weight:700;">{html.escape(str(context.get('curr', '')))}</div>
				<div style="position:absolute;right:28px;top:215px;font-size:34px;font-weight:700;">{html.escape(str(context.get('price', '')))}</div>
				<div style="position:absolute;left:18px;top:26px;font-size:20px;font-weight:700;">EXPE</div>
			</div>
		"""
	else:
		label_body = f"""
			<div style="{style}">
				<div style="position:absolute;left:14px;top:18px;font-weight:700;font-size:16px;">EXPERTS L.L.C</div>
				<div style="position:absolute;left:14px;top:58px;font-size:14px;max-width:90%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</div>
				<div style="position:absolute;left:38px;top:92px;width:220px;height:48px;background:repeating-linear-gradient(90deg,#111 0 2px,#fff 2px 4px,#111 4px 5px,#fff 5px 8px);"></div>
				<div style="position:absolute;left:48px;top:148px;font-size:20px;letter-spacing:1px;">{barcode}</div>
				<div style="position:absolute;right:18px;bottom:18px;font-size:24px;font-weight:700;">{price}</div>
			</div>
		"""
	return f"""
		<div style="display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;">
			{label_body}
			<div style="max-width:360px;color:#475569;font-size:13px;line-height:1.5;">
				<b>Approximate preview</b><br>
				This is for layout guidance. The real Zebra output comes from the rendered ZPL.
			</div>
		</div>
	"""


def send_label_to_configured_printer(label, zpl, label_count=1):
	print_method = label.get("print_method") or "Network Printer"
	if print_method == "System Printer":
		if not label.get("printer_name"):
			frappe.throw(_("Please set Printer Name on Zebra Label Format {0}.").format(label.name))
		send_to_system_printer(label.printer_name, zpl, label.name)
		if label_count > 1:
			return _("Sent {0} label(s) to printer {1}.").format(label_count, label.printer_name)
		return _("Sent to printer {0}.").format(label.printer_name)

	if not label.printer_ip:
		frappe.throw(_("Please set Printer IP on Zebra Label Format {0}.").format(label.name))
	send_to_network_printer(label.printer_ip, cint(label.printer_port) or 9100, zpl, label.name)
	if label_count > 1:
		return _("Sent {0} label(s) to printer {1}.").format(label_count, label.printer_ip)
	return _("Sent to printer {0}.").format(label.printer_ip)


def send_to_network_printer(ip, port, zpl, label_format=None):
	try:
		with socket.create_connection((ip, port), timeout=5) as conn:
			conn.sendall(zpl.encode("utf-8"))
	except OSError as exc:
		label_text = _(" for {0}").format(label_format) if label_format else ""
		frappe.throw(
			_("Could not connect to Zebra printer{0} at {1}:{2}. Please check Printer IP, port, network, and printer power. Error: {3}").format(
				label_text,
				ip,
				port,
				exc,
			)
		)


def send_to_system_printer(printer_name, zpl, label_format=None):
	if os.name == "nt":
		send_to_windows_system_printer(printer_name, zpl, label_format)
	else:
		send_to_cups_printer(printer_name, zpl, label_format)


def send_to_cups_printer(printer_name, zpl, label_format=None):
	command = get_cups_print_command(printer_name)
	try:
		subprocess.run(command, input=zpl.encode("utf-8"), check=True, capture_output=True)
	except FileNotFoundError:
		frappe.throw(_("Could not find lp or lpr on this server. Install CUPS or use Network Printer mode."))
	except subprocess.CalledProcessError as exc:
		throw_system_printer_error(printer_name, label_format, exc.stderr or exc.stdout or exc)


def get_cups_print_command(printer_name):
	if shutil.which("lp"):
		return ["lp", "-d", printer_name, "-o", "raw"]
	if shutil.which("lpr"):
		return ["lpr", "-P", printer_name, "-o", "raw"]
	return ["lp", "-d", printer_name, "-o", "raw"]


def send_to_windows_system_printer(printer_name, zpl, label_format=None):
	temp_file = None
	try:
		with tempfile.NamedTemporaryFile("w", suffix=".zpl", delete=False, encoding="utf-8") as handle:
			handle.write(zpl)
			temp_file = handle.name
		subprocess.run(["print", f"/D:{printer_name}", temp_file], check=True, capture_output=True)
	except FileNotFoundError:
		frappe.throw(_("Could not find the Windows print command on this server."))
	except subprocess.CalledProcessError as exc:
		throw_system_printer_error(printer_name, label_format, exc.stderr or exc.stdout or exc)
	finally:
		if temp_file:
			try:
				os.unlink(temp_file)
			except OSError:
				pass


def throw_system_printer_error(printer_name, label_format=None, details=None):
	label_text = _(" for {0}").format(label_format) if label_format else ""
	frappe.throw(
		_("Could not print Zebra label{0} to system printer {1}. Please check the printer name and server print setup. Error: {2}").format(
			label_text,
			printer_name,
			get_error_text(details),
		)
	)


def get_error_text(details):
	if isinstance(details, bytes):
		return details.decode("utf-8", errors="replace").strip()
	return str(details or "").strip()

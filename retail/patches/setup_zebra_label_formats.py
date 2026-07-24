import json

import frappe


SHELF_LABEL_ZPL = """^XA
^SZ2^JMA
^MCY^PMN
^PW480^MTT
^JZY
^LH0,0^LRN
^XZ
^XA
^FO10,157
^BY2^BCN,87,N,N^FD>;{barcode}^FS
^FT62,263
^CI0
^A0N,17,23^FD{barcodetext}^FS
^FT338,195
^A0N,39,49^FD{curr}^FS
^FT282,253
^A0N,42,53^FD{price}^FS
^FT17,94
^A0N,23,30^FD{productnameenglish}^FS
^FT19,40
^A0N,23,30^FDEXPE^FS
^FT17,131
^A0N,23,30^FD{productnameenglish1}^FS
^PQ{copies},0,1,Y
^XZ"""


BARCODE_LABEL_ZPL = """^XA
^SZ2^JMA
^MCY^PMN
^PW305
^JZY
^LH0,0^LRN
^XZ
^XA
^FT18,39
^CI0
^A0N,20,27^FDEXPERTS L.L.C^FS
^FT55,46
^A0N,17,24^FD^FS
^FT15,80
^A0N,13,25^FD{productnameenglish}^FS
^FO40,91
^BY2^BCN,44,N,N^FD>;{barcode}^FS
^FT47,157
^A0N,23,34^FD{barcodetext}^FS
^FT124,190
^A0N,28,38^FD{curr} {price}^FS
^PQ{copies},0,1,Y
^XZ"""


def execute():
	create_label_format(
		name="Shelf Label",
		label_type="Shelf Label",
		width_dots=480,
		height_dots=320,
		zpl_template=SHELF_LABEL_ZPL,
		is_default=0,
	)
	create_label_format(
		name="Barcode Label",
		label_type="Barcode Label",
		width_dots=305,
		height_dots=210,
		zpl_template=BARCODE_LABEL_ZPL,
		is_default=1,
	)
	add_items_workspace_link()


def create_label_format(name, label_type, width_dots, height_dots, zpl_template, is_default=0):
	values = {
		"label_name": name,
		"enabled": 1,
		"is_default": is_default,
		"label_type": label_type,
		"reference_doctype": "Item",
		"width_dots": width_dots,
		"height_dots": height_dots,
		"dpi": 203,
		"default_copies": 1,
		"currency": "AED",
		"printer_port": 9100,
		"zpl_template": zpl_template,
	}
	if frappe.db.exists("Zebra Label Format", name):
		doc = frappe.get_doc("Zebra Label Format", name)
		doc.update(values)
		doc.save(ignore_permissions=True)
		return

	doc = frappe.get_doc({"doctype": "Zebra Label Format", **values})
	doc.insert(ignore_permissions=True)


def add_items_workspace_link():
	if not frappe.db.exists("Workspace", "Items"):
		return

	workspace = frappe.get_doc("Workspace", "Items")
	changed = False

	if not any(link.link_to == "Zebra Label Format" for link in workspace.links):
		for link in workspace.links:
			if link.type == "Card Break" and link.label == "Item Masters":
				link.link_count = (link.link_count or 0) + 1
				break
		workspace.append(
			"links",
			{
				"type": "Link",
				"label": "Zebra Label Formats",
				"link_type": "DocType",
				"link_to": "Zebra Label Format",
				"hidden": 0,
				"is_query_report": 0,
				"onboard": 0,
				"link_count": 0,
			},
		)
		changed = True

	content = json.loads(workspace.content or "[]")
	if not any(block.get("id") == "sc_zebra_label_formats" for block in content):
		insert_at = next(
			(i for i, block in enumerate(content) if block.get("id") == "sp_items_charts"),
			len(content),
		)
		content.insert(
			insert_at,
			{
				"id": "sc_zebra_label_formats",
				"type": "shortcut",
				"data": {"shortcut_name": "Zebra Label Formats", "col": 3},
			},
		)
		workspace.content = json.dumps(content, separators=(",", ":"))
		changed = True

	if not any(shortcut.label == "Zebra Label Formats" for shortcut in workspace.shortcuts):
		workspace.append(
			"shortcuts",
			{
				"label": "Zebra Label Formats",
				"type": "DocType",
				"link_to": "Zebra Label Format",
				"doc_view": "List",
				"color": "Blue",
				"stats_filter": "[]",
			},
		)
		changed = True

	if changed:
		workspace.save(ignore_permissions=True)

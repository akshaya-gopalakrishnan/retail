import json

import frappe


def execute():
	create_pos_workspace()
	create_pos_child_workspaces()
	frappe.clear_cache()


def create_pos_workspace():
	available_shortcuts = get_available_shortcuts()
	content = [
		{"id": "hdr_pos", "type": "header", "data": {"text": '<span class="h4">POS</span>', "col": 12}},
		*[
			{
				"id": f"sc_{shortcut.lower().replace(' ', '_')}",
				"type": "shortcut",
				"data": {"shortcut_name": shortcut, "col": 3},
			}
			for shortcut in available_shortcuts
		],
		{"id": "sp_pos_reports", "type": "spacer", "data": {"col": 12}},
		*[
			{
				"id": f"sc_{shortcut.lower().replace(' ', '_')}",
				"type": "shortcut",
				"data": {"shortcut_name": shortcut, "col": 3},
			}
			for shortcut in get_available_report_shortcuts()
		],
	]

	links = get_available_links()

	doc = frappe.get_doc("Workspace", "POS") if frappe.db.exists("Workspace", "POS") else frappe.new_doc("Workspace")
	doc.update(
		{
			"label": "POS",
			"title": "POS",
			"module": "Retail-app",
			"icon": "pos",
			"indicator_color": "blue",
			"is_hidden": 0,
			"hide_custom": 0,
			"public": 1,
			"content": json.dumps(content),
			"charts": [],
			"shortcuts": [],
			"links": [],
		}
	)

	for shortcut in get_pos_workspace_shortcuts():
		doc.append("shortcuts", shortcut)

	for link in links:
		row = link.copy()
		row.setdefault("hidden", 0)
		row.setdefault("onboard", 0)
		row.setdefault("is_query_report", 0)
		row.setdefault("link_count", 0)
		doc.append("links", row)

	doc.save(ignore_permissions=True)


def create_pos_child_workspaces():
	child_workspaces = [
		{
			"title": "POS Invoices",
			"icon": "file",
			"quick_list": {"label": "POS Invoices", "document_type": "POS Invoice"},
		},
		{
			"title": "POS Profiles",
			"icon": "users",
			"quick_list": {"label": "POS Profiles", "document_type": "POS Profile"},
		},
		{
			"title": "POS Counters",
			"icon": "dialpad",
			"quick_list": {"label": "POS Counters", "document_type": "POS Branch Counter"},
		},
		{
			"title": "POS Cashier Shifts",
			"icon": "hr",
			"quick_list": {"label": "POS Cashier Shifts", "document_type": "POS Cashier Shift"},
		},
		{
			"title": "POS Counter Sessions",
			"icon": "pos",
			"quick_list": {"label": "POS Counter Sessions", "document_type": "POS Counter Session"},
		},
		{
			"title": "POS Opening Entries",
			"icon": "up-arrow",
			"quick_list": {"label": "POS Opening Entries", "document_type": "POS Opening Entry"},
		},
		{
			"title": "POS Closing Entries",
			"icon": "down-arrow",
			"quick_list": {"label": "POS Closing Entries", "document_type": "POS Closing Entry"},
		},
		{
			"title": "POS Branch Day Closings",
			"icon": "calendar",
			"quick_list": {"label": "POS Branch Day Closings", "document_type": "POS Branch Day Closing"},
		},
		{
			"title": "POS Sync Logs",
			"icon": "refresh",
			"quick_list": {"label": "POS Sync Logs", "document_type": "POS Sync Log"},
		},
		{
			"title": "POS Reports",
			"shortcuts": [
				{"label": "POS Sales Summary", "type": "Report", "link_to": "Daily Sales Summary", "report_ref_doctype": "Sales Invoice"},
				{"label": "POS Transaction Log", "type": "Report", "link_to": "Daily Transaction Log", "report_ref_doctype": "Sales Invoice"},
				{"label": "Counter Performance", "type": "Report", "link_to": "Counter Performance", "report_ref_doctype": "Sales Invoice"},
			],
		},
	]

	remove_obsolete_pos_child_workspaces()
	for index, workspace in enumerate(child_workspaces, start=1):
		create_pos_child_workspace(workspace, index)


def remove_obsolete_pos_child_workspaces():
	for workspace in ("POS Sales Invoices", "POS Payments"):
		if frappe.db.exists("Workspace", workspace):
			frappe.delete_doc("Workspace", workspace, ignore_permissions=True, force=True)


def create_pos_child_workspace(workspace, index):
	title = workspace["title"]
	doc = frappe.get_doc("Workspace", title) if frappe.db.exists("Workspace", title) else frappe.new_doc("Workspace")
	doc.update(
		{
			"label": title,
			"title": title,
			"parent_page": "POS",
			"module": "Retail-app",
			"indicator_color": "green",
			"is_hidden": 0,
			"hide_custom": 0,
			"icon": workspace.get("icon", ""),
			"public": 1,
			"sequence_id": index,
			"content": json.dumps(get_child_workspace_content(workspace)),
			"charts": [],
			"custom_blocks": [],
			"links": [],
			"number_cards": [],
			"quick_lists": [],
			"shortcuts": [],
		}
	)

	if quick_list := workspace.get("quick_list"):
		if not frappe.db.exists("DocType", quick_list["document_type"]):
			return
		row = {"quick_list_filter": "[]", **quick_list}
		doc.append("quick_lists", row)

	for shortcut in workspace.get("shortcuts", []):
		if shortcut["type"] == "Report" and not frappe.db.exists("Report", shortcut["link_to"]):
			continue
		doc.append("shortcuts", {"color": "Grey", "doc_view": "List", **shortcut})

	doc.save(ignore_permissions=True)


def get_child_workspace_content(workspace):
	title = workspace["title"]
	content = [
		{
			"id": f"hdr_{frappe.scrub(title)}",
			"type": "header",
			"data": {"text": f'<span class="h4">{title}</span>', "col": 12},
		}
	]

	if quick_list := workspace.get("quick_list"):
		content.append(
			{
				"id": f"ql_{frappe.scrub(title)}",
				"type": "quick_list",
				"data": {"quick_list_name": quick_list["label"], "col": 4},
			}
		)

	for shortcut in workspace.get("shortcuts", []):
		content.append(
			{
				"id": f"sc_{frappe.scrub(shortcut['label'])}",
				"type": "shortcut",
				"data": {"shortcut_name": shortcut["label"], "col": 4},
			}
		)

	return content


def get_pos_workspace_shortcuts():
	shortcuts = []
	for label, doctype in get_pos_doctype_links():
		if frappe.db.exists("DocType", doctype):
			shortcuts.append(
				{
					"label": label,
					"type": "DocType",
					"link_to": doctype,
					"doc_view": "List",
					"color": "Grey",
				}
			)
	for label, report in get_pos_report_links():
		if frappe.db.exists("Report", report):
			shortcuts.append(
				{
					"label": label,
					"type": "Report",
					"link_to": report,
					"doc_view": "List",
					"color": "Grey",
					"report_ref_doctype": "Sales Invoice",
				}
			)
	return shortcuts


def get_available_shortcuts():
	shortcuts = []
	for label, doctype in get_pos_doctype_links():
		if frappe.db.exists("DocType", doctype):
			shortcuts.append(label)
	return shortcuts


def get_available_report_shortcuts():
	shortcuts = []
	for label, report in get_pos_report_links():
		if frappe.db.exists("Report", report):
			shortcuts.append(label)
	return shortcuts


def get_available_links():
	document_links = []
	for label, doctype in get_pos_doctype_links():
		if frappe.db.exists("DocType", doctype):
			document_links.append({"label": label, "type": "Link", "link_type": "DocType", "link_to": doctype})

	report_links = []
	for label, report in get_pos_report_links():
		if frappe.db.exists("Report", report):
			report_links.append(
				{
					"label": label,
					"type": "Link",
					"link_type": "Report",
					"link_to": report,
					"is_query_report": 1,
					"report_ref_doctype": "Sales Invoice",
				}
			)

	links = []
	if document_links:
		links.append({"label": "POS Documents", "type": "Card Break", "link_type": "DocType", "link_count": len(document_links)})
		links.extend(document_links)
	if report_links:
		links.append({"label": "POS Reports", "type": "Card Break", "link_type": "DocType", "link_count": len(report_links)})
		links.extend(report_links)
	return links


def get_pos_doctype_links():
	return [
		("POS Invoices", "POS Invoice"),
		("POS Profile", "POS Profile"),
		("POS Counters", "POS Branch Counter"),
		("POS Cashier Shifts", "POS Cashier Shift"),
		("POS Counter Sessions", "POS Counter Session"),
		("POS Opening Entry", "POS Opening Entry"),
		("POS Closing Entry", "POS Closing Entry"),
		("POS Branch Day Closing", "POS Branch Day Closing"),
		("POS Sync Log", "POS Sync Log"),
		("Mode of Payment", "Mode of Payment"),
	]


def get_pos_report_links():
	return [
		("POS Sales Summary", "Daily Sales Summary"),
		("POS Transaction Log", "Daily Transaction Log"),
		("Counter Performance", "Counter Performance"),
	]


def get_legacy_links():
	return [
		{"label": "POS Documents", "type": "Card Break", "link_type": "DocType", "link_count": 7},
		{"label": "POS Invoices", "type": "Link", "link_type": "DocType", "link_to": "POS Invoice"},
		{"label": "POS Profile", "type": "Link", "link_type": "DocType", "link_to": "POS Profile"},
		{"label": "POS Counters", "type": "Link", "link_type": "DocType", "link_to": "POS Branch Counter"},
		{"label": "POS Opening Entry", "type": "Link", "link_type": "DocType", "link_to": "POS Opening Entry"},
		{"label": "POS Closing Entry", "type": "Link", "link_type": "DocType", "link_to": "POS Closing Entry"},
		{"label": "POS Sync Log", "type": "Link", "link_type": "DocType", "link_to": "POS Sync Log"},
		{"label": "Mode of Payment", "type": "Link", "link_type": "DocType", "link_to": "Mode of Payment"},
		{"label": "POS Reports", "type": "Card Break", "link_type": "DocType", "link_count": 3},
		{
			"label": "POS Sales Summary",
			"type": "Link",
			"link_type": "Report",
			"link_to": "Daily Sales Summary",
			"is_query_report": 1,
			"report_ref_doctype": "Sales Invoice",
		},
		{
			"label": "POS Transaction Log",
			"type": "Link",
			"link_type": "Report",
			"link_to": "Daily Transaction Log",
			"is_query_report": 1,
			"report_ref_doctype": "Sales Invoice",
		},
		{
			"label": "Counter Performance",
			"type": "Link",
			"link_type": "Report",
			"link_to": "Counter Performance",
			"is_query_report": 1,
			"report_ref_doctype": "Sales Invoice",
		},
	]

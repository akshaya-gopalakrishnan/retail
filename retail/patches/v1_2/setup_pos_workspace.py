import json

import frappe


POS_REPORT_GROUPS = (
	(
		"Sales",
		(
			("POS Sales Summary", "POS Sales Summary"),
			("POS Transaction Log", "POS Transaction Log"),
			("POS Item-wise Sales", "POS Item-wise Sales"),
			("POS Category/Item Group Sales", "POS Category Item Group Sales"),
			("Item Group Sales Analysis", "Item Group Sales Analysis"),
			("POS Hourly Sales", "POS Hourly Sales"),
			("POS Return Report", "POS Return Report"),
		),
	),
	(
		"Cashier / Counter",
		(
			("Cashier Wise Sales", "Cashier Wise Sales"),
			("Counter Wise Sales", "Counter Wise Sales"),
			("Shift Closing Variance", "Shift Closing Variance"),
			("Payment Mode Summary", "POS Payment Mode Summary"),
			("POS Discount Report", "POS Discount Report"),
			("POS Price Override Report", "POS Price Override Report"),
		),
	),
	(
		"Management Dashboard Totals",
		(
			("POS Daily Closing Summary", "POS Daily Closing Summary"),
			("POS Cash Movement Report", "POS Cash Movement Report"),
		),
	),
)
POS_REPORT_CHARTS = (
	"POS Sales Trend 7 Days",
	"POS Sales by Counter",
	"POS Top Selling Products",
)
POS_REPORT_QUICK_LINKS = (
	("POS Sales Summary", "POS Sales Summary"),
	("POS Transaction Log", "POS Transaction Log"),
	("POS Daily Closing Summary", "POS Daily Closing Summary"),
	("Payment Mode Summary", "POS Payment Mode Summary"),
	("Shift Closing Variance", "Shift Closing Variance"),
	("POS Cash Movement Report", "POS Cash Movement Report"),
)


def execute():
	create_pos_workspace()
	create_pos_child_workspaces()
	remove_pos_report_child_workspaces()
	ensure_reports_workspace_pos_section()
	frappe.clear_cache()


def create_pos_workspace():
	available_shortcuts = get_available_shortcuts()
	content = [
		{"id": "hdr_pos", "type": "header", "data": {"text": '<span class="h4">POS</span>', "col": 12}},
		*[
			{
				"id": f"sc_{content_id(shortcut)}",
				"type": "shortcut",
				"data": {"shortcut_name": shortcut, "col": 3},
			}
			for shortcut in available_shortcuts
		],
	]
	if any(frappe.db.exists("Dashboard Chart", chart) for chart in POS_REPORT_CHARTS):
		content.append({"id": "sp_pos_charts", "type": "spacer", "data": {"col": 12}})
		for chart in POS_REPORT_CHARTS:
			if frappe.db.exists("Dashboard Chart", chart):
				content.append(
					{
						"id": f"chart_{content_id(chart)}",
						"type": "chart",
						"data": {"chart_name": chart, "col": 4},
					}
				)

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

	for chart in POS_REPORT_CHARTS:
		if frappe.db.exists("Dashboard Chart", chart):
			doc.append("charts", {"chart_name": chart, "label": chart})

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
			"icon": "chart",
			"report_groups": POS_REPORT_GROUPS,
		},
	]

	remove_obsolete_pos_child_workspaces()
	for index, workspace in enumerate(child_workspaces, start=1):
		create_pos_child_workspace(workspace, index)


def remove_obsolete_pos_child_workspaces():
	for workspace in ("POS Sales Invoices", "POS Payments"):
		if frappe.db.exists("Workspace", workspace):
			frappe.delete_doc("Workspace", workspace, ignore_permissions=True, force=True)


def remove_pos_report_child_workspaces():
	for label, report in get_pos_report_links():
		for workspace in {label, report}:
			if frappe.db.exists("Workspace", workspace):
				frappe.delete_doc("Workspace", workspace, ignore_permissions=True, force=True)


def ensure_reports_workspace_pos_section():
	if not frappe.db.exists("Workspace", "Reports"):
		return

	doc = frappe.get_doc("Workspace", "Reports")
	content = json.loads(doc.content or "[]")
	if not any(row.get("type") == "card" and row.get("data", {}).get("card_name") == "POS Reports" for row in content):
		content.append({"id": "card_pos_reports", "type": "card", "data": {"card_name": "POS Reports", "col": 4}})

	pos_labels = {label for label, _report in get_pos_report_links()}
	pos_labels.add("POS Reports")
	doc.links = [
		row
		for row in doc.links
		if row.label not in pos_labels
	]
	doc.append(
		"links",
		{
			"label": "POS Reports",
			"type": "Card Break",
			"link_type": "DocType",
			"link_count": len(get_pos_report_links()),
		},
	)
	for label, report in get_pos_report_links():
		if not frappe.db.exists("Report", report):
			continue
		doc.append(
			"links",
			{
				"label": label,
				"type": "Link",
				"link_type": "Report",
				"link_to": report,
				"is_query_report": 1,
				"report_ref_doctype": get_pos_report_ref_doctype(report),
			},
		)
	doc.content = json.dumps(content)
	doc.save(ignore_permissions=True)


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

	for label, report in get_pos_report_quick_links():
		if not workspace.get("report_groups") or not frappe.db.exists("Report", report):
			continue
		doc.append(
			"shortcuts",
			{
				"color": "Grey",
				"doc_view": "List",
				"label": label,
				"type": "Report",
				"link_to": report,
				"report_ref_doctype": get_pos_report_ref_doctype(report),
			},
		)

	for group, shortcuts in workspace.get("report_groups", []):
		doc.append(
			"links",
			{
				"label": group,
				"type": "Card Break",
				"link_type": "DocType",
				"link_count": len(shortcuts),
			},
		)
		for label, report in shortcuts:
			if not frappe.db.exists("Report", report):
				continue
			doc.append(
				"links",
				{
					"label": label,
					"type": "Link",
					"link_type": "Report",
					"link_to": report,
					"is_query_report": 1,
					"report_ref_doctype": get_pos_report_ref_doctype(report),
				},
			)

	doc.save(ignore_permissions=True)


def get_child_workspace_content(workspace):
	title = workspace["title"]
	content = [
		{
			"id": f"hdr_{content_id(title)}",
			"type": "header",
			"data": {"text": f'<span class="h4">{title}</span>', "col": 12},
		}
	]

	if quick_list := workspace.get("quick_list"):
		content.append(
			{
				"id": f"ql_{content_id(title)}",
				"type": "quick_list",
				"data": {"quick_list_name": quick_list["label"], "col": 4},
			}
		)

	for shortcut in workspace.get("shortcuts", []):
		content.append(
			{
				"id": f"sc_{content_id(shortcut['label'])}",
				"type": "shortcut",
				"data": {"shortcut_name": shortcut["label"], "col": 4},
			}
		)

	if workspace.get("report_groups"):
		for label, report in get_pos_report_quick_links():
			if not frappe.db.exists("Report", report):
				continue
			content.append(
				{
					"id": f"sc_{content_id(label)}",
					"type": "shortcut",
					"data": {"shortcut_name": label, "col": 4},
				}
			)
		content.append({"id": "sp_pos_report_cards", "type": "spacer", "data": {"col": 12}})
		for group, _shortcuts in workspace.get("report_groups", []):
			content.append(
				{
					"id": f"card_{content_id(group)}",
					"type": "card",
					"data": {"card_name": group, "col": 4},
				}
			)

	return content


def content_id(value):
	return frappe.scrub(value).replace("/", "_")


def get_pos_report_ref_doctype(report):
	if report == "Shift Closing Variance":
		return "POS Cashier Shift"
	if report == "POS Cash Movement Report":
		return "POS Cash Movement"
	return "POS Invoice"


def get_pos_report_workspace_name(label, report):
	return report if "/" in label else label


def get_pos_report_indicator(group):
	if group == "Sales":
		return "blue"
	if group == "Cashier / Counter":
		return "orange"
	return "green"


def get_pos_report_icon(label, group):
	icons = {
		"POS Transaction Log": "list",
		"POS Item-wise Sales": "stock",
		"POS Category/Item Group Sales": "organization",
		"Item Group Sales Analysis": "organization",
		"POS Hourly Sales": "time",
		"POS Return Report": "reply",
		"Cashier Wise Sales": "hr",
		"Counter Wise Sales": "pos",
		"Shift Closing Variance": "accounting",
		"Payment Mode Summary": "payment",
		"POS Discount Report": "tag",
		"POS Price Override Report": "edit",
		"POS Daily Closing Summary": "calendar",
		"POS Cash Movement Report": "money-coins",
	}
	if label in icons:
		return icons[label]
	if group == "Sales":
		return "chart"
	if group == "Cashier / Counter":
		return "users"
	return "dashboard"


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
	return shortcuts


def get_available_shortcuts():
	shortcuts = []
	for label, doctype in get_pos_doctype_links():
		if frappe.db.exists("DocType", doctype):
			shortcuts.append(label)
	return shortcuts


def get_available_links():
	document_links = []
	for label, doctype in get_pos_doctype_links():
		if frappe.db.exists("DocType", doctype):
			document_links.append({"label": label, "type": "Link", "link_type": "DocType", "link_to": doctype})

	links = []
	if document_links:
		links.append({"label": "POS Documents", "type": "Card Break", "link_type": "DocType", "link_count": len(document_links)})
		links.extend(document_links)
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
	return [report for _group, reports in POS_REPORT_GROUPS for report in reports]


def get_pos_report_quick_links():
	return POS_REPORT_QUICK_LINKS


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

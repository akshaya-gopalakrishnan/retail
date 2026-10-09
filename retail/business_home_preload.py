"""Preload Business Home definitions using the standard permission-checked loader."""

import frappe
from frappe.desk.desktop import get_desktop_page as standard_get_desktop_page
from frappe.desk.form.load import getdoc
from frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source import get_config


def _load_definition(doctype, name):
	# getdoc writes response-level docs/docinfo and may emit permission messages.
	# Keep each speculative load isolated from the workspace response.
	response = frappe.local.response
	message_log = frappe.local.message_log
	flags = frappe.local.flags
	try:
		frappe.local.response = frappe._dict(docs=[])
		frappe.local.message_log = []
		frappe.local.flags = frappe._dict(flags)
		getdoc(doctype, name)
		loaded = frappe.local.response
		if loaded.docs and loaded.get("docinfo"):
			return {"docs": loaded.docs, "docinfo": loaded.docinfo}
	except Exception:
		# Normal widget loading remains responsible for an unreadable/failed doc.
		return None
	finally:
		frappe.local.response = response
		frappe.local.message_log = message_log
		frappe.local.flags = flags


def _load_chart_config(source):
	response, messages, flags = frappe.local.response, frappe.local.message_log, frappe.local.flags
	try:
		frappe.local.response = frappe._dict(docs=[])
		frappe.local.message_log = []
		frappe.local.flags = frappe._dict(flags)
		return get_config(source)
	except Exception:
		return None
	finally:
		frappe.local.response, frappe.local.message_log, frappe.local.flags = response, messages, flags


@frappe.whitelist()
def get_desktop_page(page):
	data = standard_get_desktop_page(page)
	from retail.sidebar_permissions import filter_workspace
	data = filter_workspace(data, frappe.parse_json(page).get("name"))
	if frappe.parse_json(page).get("name") != "Business Home" or not data:
		return data

	definitions = []
	chart_configs = {}
	seen = set()
	for group, doctype, field in (
		("number_cards", "Number Card", "number_card_name"),
		("charts", "Dashboard Chart", "chart_name"),
	):
		for row in data.get(group, {}).get("items", []):
			name = row.get(field)
			key = (doctype, name)
			if not name or key in seen:
				continue
			seen.add(key)
			definition = _load_definition(doctype, name)
			if definition:
				definitions.append(definition)
				if doctype == "Dashboard Chart":
					for doc in definition["docs"]:
						if doc.get("doctype") != doctype or doc.get("chart_type") != "Custom":
							continue
						source = doc.get("source")
						if source and source not in chart_configs:
							config = _load_chart_config(source)
							if config is not None:
								chart_configs[source] = config
	data["retail_widget_definitions"] = definitions
	data["retail_chart_source_configs"] = chart_configs
	return data

import json
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import setup_custom_perms


VAN_SALES_ROLES = ("Van Sales User", "Van Sales Manager", "System Manager")
VAN_MANAGED_ROLES = ("Van Sales User", "Van Sales Manager", "Retail Price Manager")
VAN_SALES_DASHBOARD_CHARTS = (
	{"name": "Van Sales Trend 7 Days", "source": "Van Sales Trend 7 Days", "type": "Line"},
	{"name": "Van Sales by Van", "source": "Van Sales by Van", "type": "Bar"},
	{"name": "Van Top Selling Products", "source": "Van Top Selling Products", "type": "Bar"},
)
VAN_FIELD_DEPENDS_ON = "eval:doc.custom_is_van_stock_entry==1"


def ensure_van_sales_metadata():
	from retail.van_assignment import setup_fields
	setup_fields()
	ensure_van_sales_roles()
	ensure_van_sales_custom_fields()
	ensure_van_sales_standard_permissions()
	ensure_van_sales_pages()
	ensure_van_sales_workspace()
	remove_legacy_van_sales_invoice()


def ensure_van_sales_pages():
	page_specs = {
		"van-stock-view": {
			"title": "Van Stock View",
			"icon": "fa fa-cubes",
			"roles": VAN_SALES_ROLES,
		},
		"van-stock-request": {
			"title": "Stock Request",
			"icon": "fa fa-list-alt",
			"roles": VAN_SALES_ROLES,
		},
		"van-stock-entries": {
			"title": "Van Stock Entries",
			"icon": "fa fa-exchange",
			"roles": VAN_SALES_ROLES,
		},
		"retail-van-sales-invoice": {
			"title": "Van Sales Invoice",
			"icon": "fa fa-truck",
			"roles": VAN_SALES_ROLES,
		},
		"van-payments": {
			"title": "Van Payments",
			"icon": "fa fa-money",
			"roles": VAN_SALES_ROLES,
		},
	}

	for page_name, spec in page_specs.items():
		ensure_van_sales_page(page_name, spec)


def ensure_van_sales_page(page_name, spec):
	truncated_page_name = page_name[:20]
	if page_name != truncated_page_name and not frappe.db.exists("Page", page_name) and frappe.db.exists("Page", truncated_page_name):
		frappe.rename_doc("Page", truncated_page_name, page_name, force=True, show_alert=False)

	page = frappe.get_doc("Page", page_name) if frappe.db.exists("Page", page_name) else frappe.new_doc("Page")
	page.name = page_name
	page.page_name = page_name
	page.title = spec["title"]
	page.module = "Retail-app"
	page.standard = "Yes"
	page.system_page = 0
	page.icon = spec["icon"]
	page.content = None
	page.roles = []
	for role in spec["roles"]:
		page.append("roles", {"role": role})
	page.save(ignore_permissions=True)

	if page.name != page_name and not frappe.db.exists("Page", page_name):
		frappe.rename_doc("Page", page.name, page_name, force=True, show_alert=False)


def ensure_van_stock_view_page():
	ensure_van_sales_page(
		"van-stock-view",
		{
			"title": "Van Stock View",
			"icon": "fa fa-cubes",
			"roles": VAN_SALES_ROLES,
		},
	)


def ensure_van_stock_request_page():
	ensure_van_sales_page(
		"van-stock-request",
		{
			"title": "Stock Request",
			"icon": "fa fa-list-alt",
			"roles": VAN_SALES_ROLES,
		},
	)


def _read_retail_file(relative_path):
	path = Path(frappe.get_app_path("retail")) / relative_path
	return path.read_text(encoding="utf-8")


def remove_legacy_van_sales_invoice():
	for page_name in ("van-sales-invoice",):
		if frappe.db.exists("Page", page_name):
			frappe.delete_doc("Page", page_name, ignore_permissions=True, force=True)

	for doctype in ("Van Sales Invoice", "Van Sales Invoice Item"):
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, ignore_permissions=True, force=True)

	frappe.db.commit()
	frappe.clear_cache()


def ensure_van_sales_roles():
	for role_name in VAN_MANAGED_ROLES:
		role = frappe.get_doc("Role", role_name) if frappe.db.exists("Role", role_name) else frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = 1
		role.disabled = 0
		role.save(ignore_permissions=True)


def ensure_van_sales_custom_fields():
	create_custom_fields(
		{
			"Customer": [
				{
					"fieldname": "custom_is_van_customer",
					"label": "Is Van Customer",
					"fieldtype": "Check",
					"insert_after": "customer_name",
					"hidden": 1,
					"in_list_view": 0,
					"in_standard_filter": 0,
				},
			],
			"Sales Invoice": [
				{
					"fieldname": "custom_section_break_ys8q0",
					"fieldtype": "Section Break",
					"insert_after": "amended_from",
				},
				{
					"fieldname": "custom_is_van_sale",
					"label": "Is Van Sale",
					"fieldtype": "Check",
					"insert_after": "custom_section_break_ys8q0",
					"hidden": 1,
					"in_list_view": 0,
					"in_standard_filter": 0,
				},
				{
					"fieldname": "custom_van_session",
					"label": "Van Session",
					"fieldtype": "Link",
					"options": "Van Session",
					"insert_after": "custom_is_van_sale",
					"depends_on": "eval:doc.custom_is_van_sale",
				},
				{
					"fieldname": "custom_van",
					"label": "Van",
					"fieldtype": "Link",
					"options": "Van Fleet",
					"insert_after": "custom_van_session",
					"depends_on": "eval:doc.custom_is_van_sale",
					"fetch_from": "custom_van_session.van",
					"read_only": 1,
				},
				{
					"fieldname": "custom_column_break_lwxjd",
					"fieldtype": "Column Break",
					"insert_after": "custom_van",
				},
				{
					"fieldname": "custom_van_warehouse",
					"label": "Van Warehouse",
					"fieldtype": "Link",
					"options": "Warehouse",
					"insert_after": "custom_column_break_lwxjd",
					"depends_on": "eval:doc.custom_is_van_sale",
					"fetch_from": "custom_van_session.van_warehouse",
					"read_only": 1,
				},
				{
					"fieldname": "custom_driver",
					"label": "Driver",
					"fieldtype": "Link",
					"options": "Driver",
					"insert_after": "custom_van_warehouse",
					"depends_on": "eval:doc.custom_is_van_sale",
					"fetch_from": "custom_van_session.driver",
					"read_only": 1,
				},
				{
					"fieldname": "custom_driver_name",
					"label": "Driver Name",
					"fieldtype": "Data",
					"insert_after": "custom_driver",
					"depends_on": "eval:doc.custom_is_van_sale",
					"fetch_from": "custom_van_session.driver_name",
					"read_only": 1,
				},
			],
			"Payment Entry": [
				{
					"fieldname": "custom_section_break_qxzwe",
					"fieldtype": "Section Break",
					"insert_after": "mode_of_payment",
				},
				{
					"fieldname": "custom_is_van_payment",
					"label": "Is Van Payment",
					"fieldtype": "Check",
					"insert_after": "custom_section_break_qxzwe",
					"hidden": 1,
					"in_list_view": 0,
					"in_standard_filter": 0,
				},
				{
					"fieldname": "custom_van_session",
					"label": "Van Session",
					"fieldtype": "Link",
					"options": "Van Session",
					"insert_after": "custom_is_van_payment",
					"depends_on": "eval:doc.custom_is_van_payment",
				},
				{
					"fieldname": "custom_van",
					"label": "Van",
					"fieldtype": "Link",
					"options": "Van Fleet",
					"insert_after": "custom_van_session",
					"depends_on": "eval:doc.custom_is_van_payment",
					"fetch_from": "custom_van_session.van",
					"read_only": 1,
				},
				{
					"fieldname": "custom_column_break_pfdm4",
					"fieldtype": "Column Break",
					"insert_after": "custom_van",
				},
				{
					"fieldname": "custom_driver",
					"label": "Driver",
					"fieldtype": "Link",
					"options": "Driver",
					"insert_after": "custom_column_break_pfdm4",
					"depends_on": "eval:doc.custom_is_van_payment",
					"fetch_from": "custom_van_session.driver",
					"read_only": 1,
				},
				{
					"fieldname": "custom_driver_name",
					"label": "Driver Name",
					"fieldtype": "Data",
					"insert_after": "custom_driver",
					"depends_on": "eval:doc.custom_is_van_payment",
					"fetch_from": "custom_van_session.driver_name",
					"read_only": 1,
				},
			],
			"Stock Entry": [
				{
					"fieldname": "custom_section_break_hwoog",
					"fieldtype": "Section Break",
					"insert_after": "apply_putaway_rule",
				},
				{
					"fieldname": "custom_is_van_stock_entry",
					"label": "Is Van Stock Entry",
					"fieldtype": "Check",
					"insert_after": "custom_section_break_hwoog",
					"hidden": 1,
					"in_list_view": 0,
					"in_standard_filter": 0,
				},
				{
					"fieldname": "custom_van_session",
					"label": "Van Session",
					"fieldtype": "Link",
					"options": "Van Session",
					"insert_after": "custom_is_van_stock_entry",
					"depends_on": VAN_FIELD_DEPENDS_ON,
					"in_list_view": 0,
					"in_standard_filter": 0,
				},
				{
					"fieldname": "custom_van",
					"label": "Van",
					"fieldtype": "Link",
					"options": "Van Fleet",
					"insert_after": "custom_van_session",
					"depends_on": VAN_FIELD_DEPENDS_ON,
					"fetch_from": "custom_van_session.van",
					"in_list_view": 0,
					"in_standard_filter": 0,
					"read_only": 1,
				},
				{
					"fieldname": "custom_van_stock_entry_type",
					"label": "Van Stock Entry Type",
					"fieldtype": "Select",
					"options": "Loading\nReloading\nOffloading\nWastage",
					"insert_after": "custom_van",
					"depends_on": VAN_FIELD_DEPENDS_ON,
					"in_list_view": 0,
					"in_standard_filter": 0,
				},
				{
					"fieldname": "custom_column_break_glsno",
					"fieldtype": "Column Break",
					"insert_after": "custom_van_stock_entry_type",
				},
				{
					"fieldname": "custom_van_warehouse",
					"label": "Van Warehouse",
					"fieldtype": "Link",
					"options": "Warehouse",
					"insert_after": "custom_column_break_glsno",
					"depends_on": VAN_FIELD_DEPENDS_ON,
					"fetch_from": "custom_van_session.van_warehouse",
					"read_only": 1,
				},
				{
					"fieldname": "custom_driver",
					"label": "Driver",
					"fieldtype": "Link",
					"options": "Driver",
					"insert_after": "custom_van_warehouse",
					"depends_on": VAN_FIELD_DEPENDS_ON,
					"fetch_from": "custom_van_session.driver",
					"read_only": 1,
				},
				{
					"fieldname": "custom_driver_name_",
					"label": "Driver Name",
					"fieldtype": "Data",
					"insert_after": "custom_driver",
					"depends_on": VAN_FIELD_DEPENDS_ON,
					"fetch_from": "custom_van_session.driver_name",
					"in_list_view": 0,
					"in_standard_filter": 0,
					"read_only": 1,
				},
				{
					"fieldname": "custom_van_warehouse_stock",
					"label": "Van Warehouse Stock",
					"fieldtype": "HTML",
					"insert_after": "get_stock_and_rate",
					"depends_on": VAN_FIELD_DEPENDS_ON,
				},
			],
			"Material Request": [
				{
					"fieldname": "custom_van_stock_request_section",
					"fieldtype": "Section Break",
					"insert_after": "schedule_date",
					"hidden": 1,
				},
				{
					"fieldname": "custom_is_van_stock_request",
					"label": "Is Van Stock Request",
					"fieldtype": "Check",
					"insert_after": "custom_van_stock_request_section",
					"hidden": 1,
					"in_standard_filter": 0,
					"in_list_view": 0,
				},
				{
					"fieldname": "custom_van_request_type",
					"label": "Van Request Type",
					"fieldtype": "Select",
					"options": "Loading\nReloading",
					"insert_after": "custom_is_van_stock_request",
					"depends_on": "eval:doc.custom_is_van_stock_request==1",
					"in_standard_filter": 0,
					"in_list_view": 0,
				},
				{
					"fieldname": "custom_van_session",
					"label": "Van Session",
					"fieldtype": "Link",
					"options": "Van Session",
					"insert_after": "custom_van_request_type",
					"depends_on": "eval:doc.custom_is_van_stock_request==1",
					"in_standard_filter": 0,
					"in_list_view": 0,
				},
				{
					"fieldname": "custom_van",
					"label": "Van",
					"fieldtype": "Link",
					"options": "Van Fleet",
					"insert_after": "custom_van_session",
					"depends_on": "eval:doc.custom_is_van_stock_request==1",
					"fetch_from": "custom_van_session.van",
					"read_only": 1,
					"in_standard_filter": 0,
					"in_list_view": 0,
				},
				{
					"fieldname": "custom_van_stock_request_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_van",
				},
				{
					"fieldname": "custom_van_warehouse",
					"label": "Van Warehouse",
					"fieldtype": "Link",
					"options": "Warehouse",
					"insert_after": "custom_van_stock_request_column",
					"depends_on": "eval:doc.custom_is_van_stock_request==1",
					"fetch_from": "custom_van_session.van_warehouse",
					"read_only": 1,
					"in_standard_filter": 0,
					"in_list_view": 0,
				},
				{
					"fieldname": "custom_driver",
					"label": "Driver",
					"fieldtype": "Link",
					"options": "Driver",
					"insert_after": "custom_van_warehouse",
					"depends_on": "eval:doc.custom_is_van_stock_request==1",
					"fetch_from": "custom_van_session.driver",
					"read_only": 1,
					"in_standard_filter": 0,
					"in_list_view": 0,
				},
				{
					"fieldname": "custom_driver_name",
					"label": "Driver Name",
					"fieldtype": "Data",
					"insert_after": "custom_driver",
					"depends_on": "eval:doc.custom_is_van_stock_request==1",
					"fetch_from": "custom_van_session.driver_name",
					"read_only": 1,
					"in_standard_filter": 0,
					"in_list_view": 0,
				},
			],
		},
		update=True,
	)
	normalize_van_custom_field_visibility()
	for doctype in ("Customer", "Sales Invoice", "Payment Entry", "Stock Entry", "Material Request"):
		frappe.clear_cache(doctype=doctype)


def normalize_van_custom_field_visibility():
	van_fields_by_doctype = {
		"Customer": ("custom_is_van_customer",),
		"Sales Invoice": (
			"custom_is_van_sale",
			"custom_van_session",
			"custom_van",
			"custom_van_warehouse",
			"custom_driver",
			"custom_driver_name",
		),
		"Payment Entry": (
			"custom_is_van_payment",
			"custom_van_session",
			"custom_van",
			"custom_driver",
			"custom_driver_name",
		),
		"Stock Entry": (
			"custom_is_van_stock_entry",
			"custom_van_session",
			"custom_van",
			"custom_van_stock_entry_type",
			"custom_van_warehouse",
			"custom_driver",
			"custom_driver_name_",
		),
		"Material Request": (
			"custom_is_van_stock_request",
			"custom_van_request_type",
			"custom_van_session",
			"custom_van",
			"custom_van_warehouse",
			"custom_driver",
			"custom_driver_name",
		),
	}

	for doctype, fieldnames in van_fields_by_doctype.items():
		for fieldname in fieldnames:
			custom_field = frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname})
			if not custom_field:
				continue

			values = {
				"in_standard_filter": 0,
				"in_list_view": 0,
			}
			if fieldname.startswith("custom_is_van_"):
				values["hidden"] = 1
			frappe.db.set_value("Custom Field", custom_field, values)


def ensure_van_sales_standard_permissions():
	# Driver permissions belong to Role Permission Manager, not Van Sales setup.
	# Preserve existing administrator-managed permissions, including custom rows.
	for doctype, rows in _van_sales_permission_matrix().items():
		if frappe.db.exists("DocType", doctype):
			setup_custom_perms(doctype)
			for row in rows:
				ensure_custom_docperm(doctype, row["role"], row)
			frappe.clear_cache(doctype=doctype)


def ensure_custom_docperm(doctype, role, values):
	filters = {"parent": doctype, "role": role, "permlevel": values.get("permlevel", 0), "if_owner": 0}
	name = frappe.db.get_value("Custom DocPerm", filters)
	doc = frappe.get_doc("Custom DocPerm", name) if name else frappe.new_doc("Custom DocPerm")
	doc.update(
		{
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": values.get("permlevel", 0),
			"if_owner": 0,
		}
	)
	for key in (
		"select",
		"read",
		"write",
		"create",
		"delete",
		"submit",
		"cancel",
		"amend",
		"report",
		"export",
		"import",
		"print",
		"email",
		"share",
	):
		doc.set(key, 1 if values.get(key) else 0)
	doc.save(ignore_permissions=True)


def _perm(role, **values):
	row = {
		"role": role,
		"permlevel": 0,
		"select": 0,
		"read": 0,
		"write": 0,
		"create": 0,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"report": 0,
		"export": 0,
		"import": 0,
		"print": 0,
		"email": 0,
		"share": 0,
	}
	row.update(values)
	return row


def _manager_transaction_perm(role):
	return _perm(
		role,
		read=1,
		write=1,
		create=1,
		submit=1,
		cancel=1,
		amend=1,
		report=1,
		export=1,
		print=1,
		email=1,
	)


def _user_transaction_perm(role):
	return _perm(role, read=1, write=1, create=1, submit=1, print=1)


def _van_sales_permission_matrix():
	return {
		"Sales Invoice": [
			_manager_transaction_perm("Van Sales Manager"),
			_user_transaction_perm("Van Sales User"),
		],
		"Stock Entry": [
			_manager_transaction_perm("Van Sales Manager"),
			_user_transaction_perm("Van Sales User"),
		],
		"Material Request": [
			_manager_transaction_perm("Van Sales Manager"),
			_user_transaction_perm("Van Sales User"),
		],
		"Payment Entry": [
			_manager_transaction_perm("Van Sales Manager"),
			_user_transaction_perm("Van Sales User"),
		],
		"Customer": [
			_perm(
				"Van Sales Manager",
				read=1,
				write=1,
				create=1,
				report=1,
				export=1,
				print=1,
				email=1,
			),
			_perm("Van Sales User", read=1, write=1, create=1, print=1),
		],
		"Item": [
			_perm("Van Sales Manager", read=1, report=1, export=1, print=1),
			_perm("Van Sales User", read=1),
		],
		"Warehouse": [
			_perm("Van Sales Manager", read=1, report=1, export=1, print=1),
			_perm("Van Sales User", read=1),
		],
		"Item Price": [
			_perm("Retail Price Manager", read=1, write=1, create=1, delete=1, export=1),
		],
	}


def ensure_van_customer_field():
	if frappe.db.exists("Custom Field", {"dt": "Customer", "fieldname": "custom_is_van_customer"}):
		return "exists"

	custom_field = frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Customer",
			"label": "Is Van Customer",
			"fieldname": "custom_is_van_customer",
			"fieldtype": "Check",
			"insert_after": "customer_name",
			"hidden": 1,
			"in_list_view": 0,
			"in_standard_filter": 0,
		}
	)
	custom_field.insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.clear_cache(doctype="Customer")
	return "created"


def ensure_van_stock_entry_fields():
	if frappe.db.exists("Custom Field", {"dt": "Stock Entry", "fieldname": "custom_van_warehouse_stock"}):
		custom_field = frappe.get_doc("Custom Field", {"dt": "Stock Entry", "fieldname": "custom_van_warehouse_stock"})
		custom_field.label = "Van Warehouse Stock"
		custom_field.fieldtype = "HTML"
		custom_field.insert_after = "get_stock_and_rate"
		custom_field.depends_on = "eval:doc.custom_is_van_stock_entry==1"
		custom_field.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.clear_cache(doctype="Stock Entry")
		return "exists"

	custom_field = frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Stock Entry",
			"label": "Van Warehouse Stock",
			"fieldname": "custom_van_warehouse_stock",
			"fieldtype": "HTML",
			"insert_after": "get_stock_and_rate",
			"depends_on": "eval:doc.custom_is_van_stock_entry==1",
		}
	)
	custom_field.insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.clear_cache(doctype="Stock Entry")
	return "created"


def ensure_van_sales_dashboard_charts():
	if not frappe.db.table_exists("Dashboard Chart Source") or not frappe.db.table_exists("Dashboard Chart"):
		return

	for chart_info in VAN_SALES_DASHBOARD_CHARTS:
		if not frappe.db.exists("Dashboard Chart Source", chart_info["source"]):
			source = frappe.new_doc("Dashboard Chart Source")
			source.update(
				{
					"source_name": chart_info["source"],
					"module": "Retail-app",
					"timeseries": 0,
				}
			)
			source.save(ignore_permissions=True)

		chart = frappe.get_doc("Dashboard Chart", chart_info["name"]) if frappe.db.exists("Dashboard Chart", chart_info["name"]) else frappe.new_doc("Dashboard Chart")
		chart.update(
			{
				"chart_name": chart_info["name"],
				"module": "Retail-app",
				"chart_type": "Custom",
				"document_type": "Sales Invoice",
				"source": chart_info["source"],
				"type": chart_info["type"],
				"is_public": 1,
				"is_standard": 1,
				"filters_json": "[]",
				"dynamic_filters_json": "[]",
				"timeseries": 0,
				"number_of_groups": 0,
			}
		)
		chart.flags.ignore_validate = True
		chart.save(ignore_permissions=True)


def set_workspace_roles(workspace):
	workspace.roles = []
	for role in VAN_SALES_ROLES:
		workspace.append("roles", {"role": role})


def make_workspace_content(title, shortcut_name):
	return json.dumps(
		[
			{"id": f"hdr_{frappe.scrub(title)}", "type": "header", "data": {"text": f'<span class="h4">{title}</span>', "col": 12}},
			{"id": f"sc_{frappe.scrub(shortcut_name)}", "type": "shortcut", "data": {"shortcut_name": shortcut_name, "col": 4}},
		]
	)


def make_shortcuts_workspace_content(title, shortcuts):
	content = [{"id": f"hdr_{frappe.scrub(title)}", "type": "header", "data": {"text": f'<span class="h4">{title}</span>', "col": 12}}]
	for shortcut in shortcuts:
		content.append(
			{
				"id": f"sc_{frappe.scrub(shortcut['label'])}",
				"type": "shortcut",
				"data": {"shortcut_name": shortcut["label"], "col": 3},
			}
		)
	return json.dumps(content)


def ensure_sidebar_workspace(row):
	existing_name = frappe.db.exists("Workspace", row["name"])
	if not existing_name and row.get("label"):
		existing_name = frappe.db.exists(
			"Workspace",
			{"label": row["label"], "parent_page": "Van Sales"},
		)
	if not existing_name and row.get("label"):
		existing_name = frappe.db.exists(
			"Workspace",
			{"title": row["title"], "parent_page": "Van Sales"},
		)
	if existing_name and existing_name != row["name"]:
		existing_name = frappe.rename_doc(
			"Workspace",
			existing_name,
			row["name"],
			force=True,
		)
	is_new = not existing_name
	workspace = frappe.new_doc("Workspace") if is_new else frappe.get_doc("Workspace", existing_name)
	if is_new:
		workspace.name = row["name"]
	workspace.title = row["title"]
	workspace.label = row["name"]
	workspace.module = "Retail-app"
	workspace.parent_page = "Van Sales"
	workspace.sequence_id = row["sequence_id"]
	workspace.icon = row["icon"]
	workspace.type = "Workspace"
	workspace.public = 1
	workspace.is_hidden = 0
	shortcuts = row.get("shortcuts") or [row["shortcut"]]
	workspace.content = (
		make_shortcuts_workspace_content(row.get("content_title") or row["label"], shortcuts)
		if row.get("shortcuts")
		else make_workspace_content(row.get("content_title") or row.get("label") or row["title"], row["shortcut"]["label"])
	)
	set_workspace_roles(workspace)
	workspace.shortcuts = []
	for shortcut in shortcuts:
		workspace.append("shortcuts", shortcut)
	workspace.flags.ignore_links = True
	workspace.save(ignore_permissions=True)
	return workspace.name


def ensure_van_sales_sidebar_workspaces():
	remove_replaced_van_sales_workspaces()
	report_shortcuts = (
		{"label": "Van Daily Sales Summary", "type": "Report", "link_to": "Van Daily Sales Summary"},
		{"label": "Van Daily Stock Summary", "type": "Report", "link_to": "Van Daily Stock Summary"},
		{"label": "Van Detailed Sales Summary", "type": "Report", "link_to": "Van Detailed Sales Summary"},
		{"label": "Van Profit Report", "type": "Report", "link_to": "Van Profit Report"},
		{"label": "Van Wastage Report", "type": "Report", "link_to": "Van Wastage Report"},
		{"label": "Van Outstanding Collection Summary", "type": "Report", "link_to": "Van Outstanding Collection Summary"},
	)
	rows = (
		{
			"name": "Van Sales Fleet Link",
			"title": "Van Sales Fleet Link",
			"label": "Fleet",
			"content_title": "Fleet",
			"sequence_id": 1,
			"icon": "truck",
			"shortcut": {"label": "Fleet", "type": "DocType", "link_to": "Van Fleet", "doc_view": "List"},
		},
		{
			"name": "Van Sales Driver Link",
			"title": "Van Sales Driver Link",
			"label": "Driver",
			"content_title": "Driver",
			"sequence_id": 2,
			"icon": "hr",
			"shortcut": {"label": "Driver", "type": "DocType", "link_to": "Driver", "doc_view": "List"},
		},
		{
			"name": "Van Sales Sessions Link",
			"title": "Van Sales Sessions Link",
			"label": "Van Sessions",
			"content_title": "Van Sessions",
			"sequence_id": 3,
			"icon": "recent",
			"shortcut": {"label": "Van Sessions", "type": "DocType", "link_to": "Van Session", "doc_view": "List"},
		},
		{
			"name": "Van Sales Stock Entries Link",
			"title": "Van Sales Stock Entries Link",
			"label": "Van Stock Entries",
			"content_title": "Van Stock Entries",
			"sequence_id": 5,
			"icon": "stock",
			"shortcut": {"label": "Van Stock Entries", "type": "Page", "link_to": "van-stock-entries"},
		},
		{
			"name": "Stock Request",
			"title": "Stock Request",
			"label": "Stock Request",
			"content_title": "Stock Request",
			"sequence_id": 4,
			"icon": "list",
			"shortcut": {"label": "Stock Request", "type": "URL", "url": "/app/van-stock-request"},
		},
		{
			"name": "Van Sales Stock View Link",
			"title": "Van Sales Stock View Link",
			"label": "Van Stock View",
			"content_title": "Van Stock View",
			"sequence_id": 6,
			"icon": "stock",
			"shortcut": {"label": "Van Stock View", "type": "URL", "url": "/app/van-stock-view"},
		},
		{
			"name": "Van Sales Invoice Link",
			"title": "Van Sales Invoice Link",
			"label": "Van Sales Invoice",
			"content_title": "Van Sales Invoice",
			"sequence_id": 7,
			"icon": "file",
			"shortcut": {"label": "Van Sales Invoice", "type": "Page", "link_to": "retail-van-sales-invoice"},
		},
		{
			"name": "Van Sales Payments Link",
			"title": "Van Sales Payments Link",
			"label": "Van Payments",
			"content_title": "Van Payments",
			"sequence_id": 8,
			"icon": "money",
			"shortcut": {"label": "Van Payments", "type": "Page", "link_to": "van-payments"},
		},
		{
			"name": "Van Sales Customers Link",
			"title": "Van Sales Customers Link",
			"label": "Van Customers",
			"content_title": "Van Customers",
			"sequence_id": 9,
			"icon": "users",
			"shortcut": {"label": "Van Customers", "type": "Page", "link_to": "van-customers"},
		},
		{
			"name": "Van Sales Items Link",
			"title": "Van Sales Items Link",
			"label": "Items",
			"content_title": "Items",
			"sequence_id": 10,
			"icon": "stock",
			"shortcut": {"label": "Items", "type": "DocType", "link_to": "Item", "doc_view": "List"},
		},
		{
			"name": "Van Sales Warehouses Link",
			"title": "Van Sales Warehouses Link",
			"label": "Warehouses",
			"content_title": "Warehouses",
			"sequence_id": 11,
			"icon": "warehouse",
			"shortcut": {"label": "Warehouses", "type": "DocType", "link_to": "Warehouse", "doc_view": "List"},
		},
		{
			"name": "Van Sales Reports",
			"title": "Van Sales Reports",
			"label": "Van Sales Reports",
			"content_title": "Van Sales Reports",
			"sequence_id": 12,
			"icon": "statistics",
			"shortcut": report_shortcuts[0],
			"shortcuts": report_shortcuts,
		},
	)
	workspace_names = [ensure_sidebar_workspace(row) for row in rows]
	remove_legacy_van_sales_sidebar_workspaces()
	return workspace_names


def remove_legacy_van_sales_sidebar_workspaces():
	legacy_values = (
		"Van Sales Stock Request Link",
		"Sales Stock Request",
		"Sales Stock View",
		"Stock View",
	)
	workspace_names = set()
	for value in legacy_values:
		if frappe.db.exists("Workspace", value):
			workspace_names.add(value)
		workspace_names.update(
			frappe.get_all(
				"Workspace",
				filters={"parent_page": "Van Sales", "title": value},
				pluck="name",
			)
		)
		workspace_names.update(
			frappe.get_all(
				"Workspace",
				filters={"parent_page": "Van Sales", "label": value},
				pluck="name",
			)
		)

	for workspace_name in workspace_names:
		frappe.delete_doc("Workspace", workspace_name, ignore_permissions=True, force=True)


def remove_replaced_van_sales_workspaces():
	for workspace_name in (
		"Accounts Desk",
		"Accounts Payable Desk",
		"Accounts Receivable Desk",
		"Bank Accounts Desk",
		"Brands Desk",
		"Branding Desk",
		"Business Home Desk",
		"Business Profile Desk",
		"Customers Desk",
		"Delivery Notes Desk",
		"Employee List Desk",
		"Item Family List Desk",
		"Item Groups Desk",
		"Items Desk",
		"Items List Desk",
		"Journal Entries Desk",
		"Manufacturing Desk",
		"Material Requests Desk",
		"Payments Desk",
		"POS Branch Day Closings Desk",
		"POS Cashier Shifts Desk",
		"POS Closing Entries Desk",
		"POS Counter Sessions Desk",
		"POS Counters Desk",
		"POS Desk",
		"POS Invoices Desk",
		"POS Opening Entries Desk",
		"POS Profiles Desk",
		"POS Reports Desk",
		"POS Sync Logs Desk",
		"Price Lists Desk",
		"Promotions Desk",
		"Purchase Invoices Desk",
		"Purchase Orders Desk",
		"Purchase Receipts Desk",
		"Purchase Returns Desk",
		"Purchases Desk",
		"Quotations Desk",
		"Reports Desk",
		"Request for Quotations Desk",
		"Sales Desk",
		"Sales Invoices Desk",
		"Sales Orders Desk",
		"Sales Returns Desk",
		"Serials & Batches Desk",
		"Settings Desk",
		"Stock Adjustments Desk",
		"Stock Request Desk",
		"Stock Status Desk",
		"Stock Take Desk",
		"Stocks Desk",
		"Suppliers Desk",
		"Supplier Quotations Desk",
		"System Rules Desk",
		"Taxes Desk",
		"User List Desk",
		"Van Sales Customers Link Desk",
		"Van Sales Desk",
		"Van Sales Driver Link Desk",
		"Van Sales Fleet Link Desk",
		"Van Sales Invoice Link Desk",
		"Van Sales Items Link Desk",
		"Van Sales Payments Link Desk",
		"Van Sales Reports Desk",
		"Van Sales Sessions Link Desk",
		"Van Sales Stock Entries Link Desk",
		"Van Sales Stock View Link Desk",
		"Van Sales Warehouses Link Desk",
		"Warehouses Desk",
	):
		if frappe.db.exists("Workspace", workspace_name):
			frappe.delete_doc("Workspace", workspace_name, ignore_permissions=True, force=True)
	frappe.db.commit()
	frappe.clear_cache()


def ensure_van_sales_workspace():
	ensure_van_customer_field()
	ensure_van_stock_entry_fields()
	ensure_van_sales_dashboard_charts()
	is_new = not frappe.db.exists("Workspace", "Van Sales")
	workspace = frappe.new_doc("Workspace") if is_new else frappe.get_doc("Workspace", "Van Sales")
	workspace.title = "Van Sales"
	workspace.label = "Van Sales"
	workspace.module = "Retail-app"
	workspace.parent_page = ""
	workspace.sequence_id = 53
	workspace.icon = "truck"
	workspace.type = "Workspace"
	workspace.public = 1
	if is_new:
		workspace.name = "Van Sales"
		workspace.is_hidden = 0
	workspace.content = json.dumps(
		[
			{"id": "hdr_van_sales", "type": "header", "data": {"text": '<span class="h4">Van Sales</span>', "col": 12}},
			{"id": "sc_van_fleet", "type": "shortcut", "data": {"shortcut_name": "Fleet", "col": 3}},
			{"id": "sc_driver", "type": "shortcut", "data": {"shortcut_name": "Driver", "col": 3}},
			{"id": "sc_van_session", "type": "shortcut", "data": {"shortcut_name": "Van Sessions", "col": 3}},
			{"id": "sc_van_stock_request", "type": "shortcut", "data": {"shortcut_name": "Stock Request", "col": 3}},
			{"id": "sc_van_stock_entries", "type": "shortcut", "data": {"shortcut_name": "Stock Entries", "col": 3}},
			{"id": "sc_van_stock_view", "type": "shortcut", "data": {"shortcut_name": "Van Stock View", "col": 3}},
			{"id": "sc_van_sales_invoice", "type": "shortcut", "data": {"shortcut_name": "Sales Invoice", "col": 3}},
			{"id": "sc_van_payments", "type": "shortcut", "data": {"shortcut_name": "Payments", "col": 3}},
			{"id": "sc_van_customers", "type": "shortcut", "data": {"shortcut_name": "Customers", "col": 3}},
			{"id": "sc_item", "type": "shortcut", "data": {"shortcut_name": "Items", "col": 3}},
			{"id": "sc_warehouse", "type": "shortcut", "data": {"shortcut_name": "Warehouses", "col": 3}},
			{"id": "sp_van_charts", "type": "spacer", "data": {"col": 12}},
			{"id": "chart_van_sales_trend_7_days", "type": "chart", "data": {"chart_name": "Van Sales Trend 7 Days", "col": 4}},
			{"id": "chart_van_sales_by_van", "type": "chart", "data": {"chart_name": "Van Sales by Van", "col": 4}},
			{"id": "chart_van_top_selling_products", "type": "chart", "data": {"chart_name": "Van Top Selling Products", "col": 4}},
			{"id": "sp_van_reports", "type": "spacer", "data": {"col": 12}},
			{"id": "sc_van_daily_sales_summary", "type": "shortcut", "data": {"shortcut_name": "Van Daily Sales Summary", "col": 3}},
			{"id": "sc_van_daily_stock_summary", "type": "shortcut", "data": {"shortcut_name": "Van Daily Stock Summary", "col": 3}},
			{"id": "sc_van_detailed_sales_summary", "type": "shortcut", "data": {"shortcut_name": "Van Detailed Sales Summary", "col": 3}},
			{"id": "sc_van_profit_report", "type": "shortcut", "data": {"shortcut_name": "Van Profit Report", "col": 3}},
			{"id": "sc_van_wastage_report", "type": "shortcut", "data": {"shortcut_name": "Van Wastage Report", "col": 3}},
			{"id": "sc_van_outstanding_collection_summary", "type": "shortcut", "data": {"shortcut_name": "Van Outstanding Collection Summary", "col": 3}},
		]
	)

	set_workspace_roles(workspace)

	workspace.charts = []
	for chart in VAN_SALES_DASHBOARD_CHARTS:
		workspace.append("charts", {"chart_name": chart["name"], "label": chart["name"]})

	workspace.shortcuts = []
	for shortcut in (
		{"label": "Fleet", "type": "DocType", "link_to": "Van Fleet", "doc_view": "List"},
		{"label": "Driver", "type": "DocType", "link_to": "Driver", "doc_view": "List"},
		{"label": "Van Sessions", "type": "DocType", "link_to": "Van Session", "doc_view": "List"},
		{"label": "Stock Request", "type": "URL", "url": "/app/van-stock-request"},
		{"label": "Stock Entries", "type": "Page", "link_to": "van-stock-entries"},
		{"label": "Van Stock View", "type": "URL", "url": "/app/van-stock-view"},
		{"label": "Sales Invoice", "type": "Page", "link_to": "retail-van-sales-invoice"},
		{"label": "Payments", "type": "Page", "link_to": "van-payments"},
		{"label": "Customers", "type": "Page", "link_to": "van-customers"},
		{"label": "Items", "type": "DocType", "link_to": "Item", "doc_view": "List"},
		{"label": "Warehouses", "type": "DocType", "link_to": "Warehouse", "doc_view": "List"},
		{"label": "Van Daily Sales Summary", "type": "Report", "link_to": "Van Daily Sales Summary"},
		{"label": "Van Daily Stock Summary", "type": "Report", "link_to": "Van Daily Stock Summary"},
		{"label": "Van Detailed Sales Summary", "type": "Report", "link_to": "Van Detailed Sales Summary"},
		{"label": "Van Profit Report", "type": "Report", "link_to": "Van Profit Report"},
		{"label": "Van Wastage Report", "type": "Report", "link_to": "Van Wastage Report"},
		{"label": "Van Outstanding Collection Summary", "type": "Report", "link_to": "Van Outstanding Collection Summary"},
	):
		workspace.append("shortcuts", shortcut)

	workspace.flags.ignore_links = True
	workspace.save(ignore_permissions=True)
	ensure_van_sales_sidebar_workspaces()
	frappe.db.commit()
	frappe.clear_cache()
	return {
		"name": workspace.name,
		"parent_page": workspace.parent_page,
		"sequence_id": workspace.sequence_id,
		"public": workspace.public,
		"is_hidden": workspace.is_hidden,
	}

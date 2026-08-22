import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


RETAIL_WORKSPACE_MODULE = "Retail-app"
HIDDEN_STANDARD_WORKSPACES = {"Home"}
VISIBLE_RETAIL_WORKSPACES = {"Business Home"}
DEFAULT_RETAIL_WORKSPACE = "Business Home"
DEFAULT_PRINT_FORMATS = {
	"Sales Invoice": "Sales Invoice - Copy",
	"Delivery Note": "Delivery Note- Copy",
}
SETTINGS_SIDEBAR_WORKSPACES = (
	{
		"name": "User List",
		"title": "User List",
		"document_type": "User",
		"quick_list_label": "Users",
		"icon": "users",
		"sequence_id": 76,
	},
	{
		"name": "Employee List",
		"title": "Employee List",
		"document_type": "Employee",
		"quick_list_label": "Employees",
		"icon": "hr",
		"sequence_id": 77,
	},
)
RETAIL_PRINT_LANGUAGES = {
	"ar": "Arabic",
	"hi": "Hindi",
	"ml": "Malayalam",
}
WEBSITE_ROUTE_REDIRECTS = (
	("/", "/app", "302"),
	("/index", "/retail-home", "302"),
)
VAN_SALES_REQUIRED_DOCTYPES = ("Van Session", "Van Fleet")
VAN_SALES_CUSTOM_FIELDS = {
	"Customer": (
		"custom_is_van_customer",
	),
	"Sales Invoice": (
		"custom_section_break_ys8q0",
		"custom_is_van_sale",
		"custom_van_session",
		"custom_van",
		"custom_column_break_lwxjd",
		"custom_van_warehouse",
		"custom_driver",
		"custom_driver_name",
	),
	"Payment Entry": (
		"custom_section_break_qxzwe",
		"custom_is_van_payment",
		"custom_van_session",
		"custom_van",
		"custom_column_break_pfdm4",
		"custom_driver",
		"custom_driver_name",
	),
	"Stock Entry": (
		"custom_section_break_hwoog",
		"custom_is_van_stock_entry",
		"custom_van_session",
		"custom_van",
		"custom_van_stock_entry_type",
		"custom_column_break_glsno",
		"custom_van_warehouse",
		"custom_driver",
		"custom_driver_name_",
		"custom_van_warehouse_stock",
	),
	"Material Request": (
		"custom_van_stock_request_section",
		"custom_is_van_stock_request",
		"custom_van_request_type",
		"custom_van_session",
		"custom_van",
		"custom_van_stock_request_column",
		"custom_van_warehouse",
		"custom_driver",
		"custom_driver_name",
	),
}
VAN_SALES_WORKSPACES = (
	"Van Sales",
	"Van Sales Sessions Link",
)


def hide_non_retail_workspaces():
	"""Keep the Desk sidebar focused on Retail's workspace tree."""
	if not frappe.db.table_exists("Workspace"):
		return

	updates = []
	for workspace in frappe.get_all("Workspace", fields=["name", "module", "public", "is_hidden"]):
		if workspace.module == RETAIL_WORKSPACE_MODULE and workspace.name not in HIDDEN_STANDARD_WORKSPACES:
			continue

		if workspace.public or not workspace.is_hidden:
			updates.append(workspace.name)

	for workspace_name in updates:
		frappe.db.set_value(
			"Workspace",
			workspace_name,
			{"public": 0, "is_hidden": 1},
			update_modified=False,
		)

	for workspace_name in VISIBLE_RETAIL_WORKSPACES:
		if frappe.db.exists("Workspace", workspace_name):
			values = {"public": 1, "is_hidden": 0}
			if workspace_name == DEFAULT_RETAIL_WORKSPACE:
				values["sequence_id"] = 0
			frappe.db.set_value("Workspace", workspace_name, values, update_modified=False)

	if updates or VISIBLE_RETAIL_WORKSPACES:
		frappe.clear_cache()


def clear_url_shortcut_link_targets():
	"""URL workspace shortcuts must not carry Dynamic Link targets."""
	if not frappe.db.table_exists("Workspace Shortcut"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabWorkspace Shortcut`
		SET link_to = NULL
		WHERE type = 'URL' AND link_to IS NOT NULL
		"""
	)


def ensure_settings_sidebar_workspaces():
	"""Expose Users and Employees as Settings sidebar child workspaces."""
	if not frappe.db.table_exists("Workspace"):
		return

	for config in SETTINGS_SIDEBAR_WORKSPACES:
		workspace = (
			frappe.get_doc("Workspace", config["name"])
			if frappe.db.exists("Workspace", config["name"])
			else frappe.new_doc("Workspace")
		)
		workspace.update(
			{
				"label": config["title"],
				"title": config["title"],
				"module": RETAIL_WORKSPACE_MODULE,
				"public": 1,
				"is_hidden": 0,
				"parent_page": "Settings",
				"icon": config["icon"],
				"indicator_color": "green",
				"sequence_id": config["sequence_id"],
				"content": (
					f'[{{"id":"ql_settings_{frappe.scrub(config["name"])}","type":"quick_list",'
					f'"data":{{"quick_list_name":"{config["quick_list_label"]}","col":4}}}}]'
				),
			}
		)
		workspace.links = []
		workspace.charts = []
		workspace.shortcuts = []
		workspace.number_cards = []
		workspace.custom_blocks = []
		workspace.quick_lists = []
		workspace.append(
			"quick_lists",
			{
				"document_type": config["document_type"],
				"label": config["quick_list_label"],
				"quick_list_filter": "[]",
			},
		)
		workspace.save(ignore_permissions=True)

	frappe.clear_cache()


def ensure_website_route_redirects():
	"""Route normal users to Desk while keeping View Website on a real page."""
	if not frappe.db.table_exists("Website Route Redirect"):
		return

	settings = frappe.get_doc("Website Settings", "Website Settings")
	for source, target, status in WEBSITE_ROUTE_REDIRECTS:
		row = next((row for row in settings.route_redirects if row.source == source), None)
		if not row:
			row = settings.append("route_redirects", {"source": source})
		row.target = target
		row.redirect_http_status = status

	settings.save(ignore_permissions=True)
	frappe.clear_cache()
	frappe.db.commit()


def ensure_default_print_formats():
	"""Keep Retail print formats as defaults after fixture sync and upgrades."""
	if not frappe.db.table_exists("Print Format") or not frappe.db.table_exists("Property Setter"):
		return

	for doctype, print_format in DEFAULT_PRINT_FORMATS.items():
		if not frappe.db.exists("Print Format", print_format):
			continue

		property_setter = f"{doctype}-main-default_print_format"
		if frappe.db.exists("Property Setter", property_setter):
			frappe.db.set_value(
				"Property Setter",
				property_setter,
				"value",
				print_format,
				update_modified=False,
			)
			continue

		make_property_setter(
			doctype,
			"main",
			"default_print_format",
			print_format,
			"Data",
			for_doctype=True,
			validate_fields_for_doctype=False,
		)

	for doctype in DEFAULT_PRINT_FORMATS:
		frappe.clear_cache(doctype=doctype)


def ensure_print_languages():
	"""Ensure required print languages are available on every site."""
	if not frappe.db.table_exists("Language"):
		return

	for language_code, language_name in RETAIL_PRINT_LANGUAGES.items():
		if frappe.db.exists("Language", language_code):
			frappe.db.set_value(
				"Language",
				language_code,
				{"language_name": language_name, "enabled": 1},
				update_modified=False,
			)
			continue

		frappe.get_doc(
			{
				"doctype": "Language",
				"language_code": language_code,
				"language_name": language_name,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)

	frappe.cache.delete_value("languages_with_name")
	frappe.cache.delete_value("languages")


def cleanup_uninstalled_van_sales_metadata():
	"""Remove Van Sales metadata from Retail-only sites.

	Van Sales currently lives in a separate app that uses the same Python package
	name as Retail. Until it is merged or renamed, Retail-only sites must not keep
	Custom Fields that link to Van Sales DocTypes.
	"""
	if not frappe.db.table_exists("DocType") or all(
		frappe.db.exists("DocType", doctype) for doctype in VAN_SALES_REQUIRED_DOCTYPES
	):
		return

	touched_doctypes = set()
	if frappe.db.table_exists("Custom Field"):
		for doctype, fieldnames in VAN_SALES_CUSTOM_FIELDS.items():
			for fieldname in fieldnames:
				custom_field = frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname})
				if not custom_field:
					continue

				frappe.delete_doc("Custom Field", custom_field, force=True, ignore_permissions=True)
				touched_doctypes.add(doctype)

	for doctype in touched_doctypes:
		frappe.clear_cache(doctype=doctype)

	removed_workspaces = False
	if frappe.db.table_exists("Workspace"):
		for workspace in VAN_SALES_WORKSPACES:
			if frappe.db.exists("Workspace", workspace):
				frappe.delete_doc("Workspace", workspace, force=True, ignore_permissions=True)
				removed_workspaces = True

	if touched_doctypes or removed_workspaces:
		frappe.clear_cache()

import frappe
from frappe.boot import get_allowed_pages, get_allowed_reports
from frappe.desk.desktop import Workspace, get_custom_reports_and_doctypes
from frappe.desk.desktop import get_workspace_sidebar_items as get_standard_workspace_sidebar_items


SYSTEM_MANAGER_ROLE = "System Manager"
ALWAYS_VISIBLE_WORKSPACES = {"Business Home"}
HIDDEN_SIDEBAR_WORKSPACES = {"Sales Stock View", "Stock View"}
SIDEBAR_DISPLAY_LABELS = {
	"Van Sales Fleet Link": "Fleet",
	"Van Sales Driver Link": "Driver",
	"Van Sales Sessions Link": "Van Sessions",
	"Van Sales Stock Entries Link": "Van Stock Entries",
	"Van Sales Stock View Link": "Van Stock View",
	"Van Sales Invoice Link": "Van Sales Invoice",
	"Van Sales Payments Link": "Van Payments",
	"Van Sales Customers Link": "Van Customers",
	"Van Sales Items Link": "Items",
	"Van Sales Warehouses Link": "Warehouses",
}
VAN_SALES_PAGES = {
	"retail-van-sales-invoice",
	"van-payments",
	"van-stock-request",
	"van-stock-entries",
	"van-stock-view",
	"van-customers",
}
ROLE_SIDEBAR_WORKSPACES = {
	"Van Sales User": {"Van Sales"},
	"Van Sales Manager": {"Van Sales"},
	"Sales User": {"Sales", "Promotions"},
	"Sales Manager": {"Sales", "Promotions"},
	"Sales Master Manager": {"Sales"},
	"Item Manager": {"Items"},
	"Retail Price Manager": {"Items", "Promotions"},
	"Stock User": {"Stocks"},
	"Stock Manager": {"Stocks"},
	"Purchase User": {"Purchases"},
	"Purchase Manager": {"Purchases"},
	"Purchase Master Manager": {"Purchases"},
	"Accounts User": {"Accounts"},
	"Accounts Manager": {"Accounts"},
	"POS User": {"POS"},
	"POS Manager": {"POS"},
	"POS Integration User": {"POS"},
	"Manufacturing User": {"Manufacturing"},
	"Manufacturing Manager": {"Manufacturing"},
	"Report Manager": {"Reports"},
	"Analytics": {"Reports"},
	"Fleet Manager": {"Van Sales"},
}
WORKSPACE_ROUTE_PERMISSIONS = {
	"Items List": (("doctype", "Item"),),
	"Item Family List": (("page", "retail-item-family-l"), ("doctype", "Item")),
	"Item Groups": (("doctype", "Item Group"),),
	"Price Lists": (("doctype", "Item Price"),),
	"Brands": (("doctype", "Brand"),),
	"Customers": (("doctype", "Customer"),),
	"Quotations": (("doctype", "Quotation"),),
	"Sales Orders": (("doctype", "Sales Order"),),
	"Sales Invoices": (("doctype", "Sales Invoice"),),
	"Sales Returns": (("doctype", "Sales Invoice"),),
	"Delivery Notes": (("doctype", "Delivery Note"),),
	"Suppliers": (("doctype", "Supplier"),),
	"Request for Quotations": (("doctype", "Request for Quotation"),),
	"Supplier Quotations": (("doctype", "Supplier Quotation"),),
	"Purchase Orders": (("doctype", "Purchase Order"),),
	"Purchase Receipts": (("doctype", "Purchase Receipt"),),
	"Purchase Invoices": (("doctype", "Purchase Invoice"),),
	"Purchase Returns": (("doctype", "Purchase Receipt"),),
	"Material Requests": (("doctype", "Material Request"),),
	"Warehouses": (("doctype", "Warehouse"),),
	"Stock Adjustments": (("doctype", "Stock Entry"),),
	"Stock Take": (("doctype", "Stock Reconciliation"),),
	"Serials & Batches": (("doctype", "Serial and Batch Bundle"),),
	"Stock Status": (("doctype", "Bin"),),
	"Bank Accounts": (("doctype", "Bank Account"),),
	"Payments": (("doctype", "Payment Entry"),),
	"Taxes": (("doctype", "Sales Taxes and Charges Template"),),
	"Journal Entries": (("doctype", "Journal Entry"),),
	"Accounts Receivable": (("report", "Accounts Receivable"),),
	"Accounts Payable": (("report", "Accounts Payable"),),
	"POS Invoices": (("doctype", "POS Invoice"),),
	"POS Profiles": (("doctype", "POS Profile"),),
	"POS Counters": (("doctype", "POS Branch Counter"),),
	"POS Opening Entries": (("doctype", "POS Opening Entry"),),
	"POS Closing Entries": (("doctype", "POS Closing Entry"),),
	"POS Cashier Shifts": (("doctype", "POS Cashier Shift"),),
	"POS Counter Sessions": (("doctype", "POS Counter Session"),),
	"POS Branch Day Closings": (("doctype", "POS Branch Day Closing"),),
	"POS Sync Logs": (("doctype", "POS Sync Log"),),
	"External POS Rate Audit": (("report", "External POS Rate Audit"), ("doctype", "External POS Rate Audit")),
	"POS Reports": (("doctype", "POS Invoice"),),
	"BOM": (("doctype", "BOM"),),
	"Production Plan": (("doctype", "Production Plan"),),
	"Work Orders": (("doctype", "Work Order"),),
	"Job Cards": (("doctype", "Job Card"),),
	"Stock Entries": (("doctype", "Stock Entry"),),
	"Quality Inspection": (("doctype", "Quality Inspection"),),
	"Van Sales Fleet Link": (("doctype", "Van Fleet"),),
	"Van Sales Driver Link": (("doctype", "Driver"),),
	"Van Sales Sessions Link": (("doctype", "Van Session"),),
	"Stock Request": (("page", "van-stock-request"),),
	"Van Sales Stock Entries Link": (("page", "van-stock-entries"), ("doctype", "Stock Entry")),
	"Van Stock View": (("page", "van-stock-view"),),
	"Van Sales Stock View Link": (("page", "van-stock-view"),),
	"Van Sales Invoice Link": (("page", "retail-van-sales-invoice"), ("doctype", "Sales Invoice")),
	"Van Sales Payments Link": (("page", "van-payments"), ("doctype", "Payment Entry")),
	"Van Sales Customers Link": (("page", "van-customers"), ("doctype", "Customer")),
	"Van Sales Items Link": (("doctype", "Item"),),
	"Van Sales Warehouses Link": (("doctype", "Warehouse"),),
	"Van Daily Sales Summary": (("report", "Van Daily Sales Summary"),),
	"Van Daily Stock Summary": (("report", "Van Daily Stock Summary"),),
	"Van Detailed Sales Summary": (("report", "Van Detailed Sales Summary"),),
	"Van Profit Report": (("report", "Van Profit Report"),),
	"Van Wastage Report": (("report", "Van Wastage Report"),),
	"Van Outstanding Collection Summary": (("report", "Van Outstanding Collection Summary"),),
}

WORKSPACE_MODULES = {
	"Sales Return": "Accounts",
	"Promotions": "Selling",
	"Promo Price": "Selling",
	"Buy X Get Y Promotion": "Selling",
	"Gift Voucher Promotion": "Selling",
	"Gift Voucher Ledger": "Selling",
	"Items": "Stock",
	"Items List": "Stock",
	"Item Family List": "Stock",
	"Item Groups": "Stock",
	"Price Lists": "Stock",
	"Brands": "Stock",
	"Stocks": "Stock",
	"Warehouses": "Stock",
	"Stock Adjustments": "Stock",
	"Stock Take": "Stock",
	"Serials & Batches": "Stock",
	"Stock Status": "Stock",
	"Sales": "Selling",
	"Customers": "Selling",
	"Quotations": "Selling",
	"Sales Orders": "Selling",
	"Sales Invoices": "Accounts",
	"Sales Returns": "Accounts",
	"Delivery Notes": "Stock",
	"POS": "Accounts",
	"POS Invoices": "Accounts",
	"POS Profiles": "Accounts",
	"POS Counters": "Accounts",
	"POS Opening Entries": "Accounts",
	"POS Closing Entries": "Accounts",
	"POS Sync Logs": "Accounts",
	"POS Reports": "Accounts",
	"POS Cashier Shifts": "Accounts",
	"POS Counter Sessions": "Accounts",
	"POS Branch Day Closings": "Accounts",
	"Purchases": "Buying",
	"Suppliers": "Buying",
	"Request for Quotations": "Buying",
	"Supplier Quotations": "Buying",
	"Purchase Orders": "Buying",
	"Purchase Receipts": "Stock",
	"Purchase Invoices": "Accounts",
	"Purchase Returns": "Accounts",
	"Material Requests": "Stock",
	"Manufacturing": "Manufacturing",
	"BOM": "Manufacturing",
	"Production Plan": "Manufacturing",
	"Work Orders": "Manufacturing",
	"Job Cards": "Manufacturing",
	"Stock Entries": "Manufacturing",
	"Quality Inspection": "Manufacturing",
	"Manufacturing Reports": "Manufacturing",
	"Manufacturing Setup": "Manufacturing",
	"Accounts": "Accounts",
	"Bank Accounts": "Accounts",
	"Payments": "Accounts",
	"Taxes": "Accounts",
	"Journal Entries": "Accounts",
	"Accounts Receivable": "Accounts",
	"Accounts Payable": "Accounts",
	"Reports": "Accounts",
	"Settings": "Setup",
	"User List": "Setup",
	"Employee List": "HR",
	"Business Profile": "Setup",
	"Branding": "Setup",
	"System Rules": "Setup",
	"Van Sales": "Van Sales",
	"Van Sales Fleet Link": "Van Sales",
	"Van Sales Driver Link": "Van Sales",
	"Van Sales Sessions Link": "Van Sales",
	"Stock Request": "Van Sales",
	"Van Sales Stock Entries Link": "Van Sales",
	"Van Stock View": "Van Sales",
	"Van Sales Stock View Link": "Van Sales",
	"Van Sales Invoice Link": "Van Sales",
	"Van Sales Payments Link": "Van Sales",
	"Van Sales Customers Link": "Van Sales",
	"Van Sales Items Link": "Van Sales",
	"Van Sales Warehouses Link": "Van Sales",
	"Van Sales Reports": "Van Sales",
}

WORKSPACE_SIDEBAR_GROUPS = {
	"Items": "Items",
	"Items List": "Items",
	"Item Family List": "Items",
	"Item Groups": "Items",
	"Price Lists": "Items",
	"Brands": "Items",
	"Sales": "Sales",
	"Customers": "Sales",
	"Quotations": "Sales",
	"Sales Orders": "Sales",
	"Sales Invoices": "Sales",
	"Sales Returns": "Sales",
	"Delivery Notes": "Sales",
	"Purchases": "Purchases",
	"Suppliers": "Purchases",
	"Request for Quotations": "Purchases",
	"Supplier Quotations": "Purchases",
	"Purchase Orders": "Purchases",
	"Purchase Receipts": "Purchases",
	"Purchase Invoices": "Purchases",
	"Purchase Returns": "Purchases",
	"Material Requests": "Purchases",
	"Stocks": "Stocks",
	"Warehouses": "Stocks",
	"Stock Adjustments": "Stocks",
	"Stock Take": "Stocks",
	"Serials & Batches": "Stocks",
	"Stock Status": "Stocks",
	"Accounts": "Accounts",
	"Bank Accounts": "Accounts",
	"Payments": "Accounts",
	"Taxes": "Accounts",
	"Journal Entries": "Accounts",
	"Accounts Receivable": "Accounts",
	"Accounts Payable": "Accounts",
	"Manufacturing": "Manufacturing",
	"BOM": "Manufacturing",
	"Production Plan": "Manufacturing",
	"Work Orders": "Manufacturing",
	"Job Cards": "Manufacturing",
	"Stock Entries": "Manufacturing",
	"Quality Inspection": "Manufacturing",
	"Manufacturing Reports": "Manufacturing",
	"Manufacturing Setup": "Manufacturing",
	"POS": "POS",
	"POS Invoices": "POS",
	"POS Profiles": "POS",
	"POS Counters": "POS",
	"POS Opening Entries": "POS",
	"POS Closing Entries": "POS",
	"POS Sync Logs": "POS",
	"POS Reports": "POS",
	"POS Cashier Shifts": "POS",
	"POS Counter Sessions": "POS",
	"POS Branch Day Closings": "POS",
	"Reports": "Reports",
	"Settings": "Settings",
	"User List": "Settings",
	"Employee List": "Settings",
	"Business Profile": "Settings",
	"Branding": "Settings",
	"System Rules": "Settings",
	"Van Sales": "Van Sales",
	"Van Sales Fleet Link": "Van Sales",
	"Van Sales Driver Link": "Van Sales",
	"Van Sales Sessions Link": "Van Sales",
	"Stock Request": "Van Sales",
	"Van Sales Stock Entries Link": "Van Sales",
	"Van Stock View": "Van Sales",
	"Van Sales Stock View Link": "Van Sales",
	"Van Sales Invoice Link": "Van Sales",
	"Van Sales Payments Link": "Van Sales",
	"Van Sales Customers Link": "Van Sales",
	"Van Sales Items Link": "Van Sales",
	"Van Sales Warehouses Link": "Van Sales",
	"Van Sales Reports": "Van Sales",
}


REPORT_SIDEBAR_GROUPS = (
	(
		"Sales Reports",
		(
			"Item Group Sales Analysis",
			"Daily Sales Summary",
			"Counter Performance",
			"Sales Payment Mode Summary",
			"Daily Transaction Log",
			"Daily Profit Report",
			"Gross Profit",
		),
	),
	(
		"Purchase Reports",
		(
			"Purchase Register",
			"Supplier Wise Returns",
		),
	),
	(
		"Stock Reports",
		(
			"Stock Balance",
			"Stock Ledger",
			"Packing Stock Balance",
			"Packing Stock Ledger",
			"Stock Movement Summary",
			"Stock Adjustment History",
			"Low Stock Reorder Report",
			"Fast Moving Items",
			"Slow Moving Items",
			"Negative Stock Report",
			"Near Expiry Report",
			"Expiry Loss",
		),
	),
	(
		"Accounts Reports",
		(
			"Accounts Receivable",
			"Accounts Payable",
			"General Ledger",
			"Trial Balance",
			"Balance Sheet",
			"Profit and Loss Statement",
		),
	),
	(
		"Tax Reports",
		(
			"Tax Report",
			"Tax Payable Report Summary",
			"Sales Tax Report",
			"Sales Day wise Tax Report",
			"Purchase Tax Report",
			"Purchase Day wise Tax Report",
		),
		"Accounts Reports",
	),
)

POS_REPORT_SIDEBAR_GROUPS = (
	(
		"POS Sales Reports",
		(
			"POS Invoice Profit",
			"POS Sales Summary",
			"POS Transaction Log",
			"POS Item-wise Sales",
			"POS Category Item Group Sales",
			"POS Hourly Sales",
			"POS Return Report",
			"Cashier Wise Sales",
			"Counter Wise Sales",
			"Shift Closing Variance",
			"POS Payment Mode Summary",
			"POS Discount Report",
			"POS Price Override Report",
			"POS Daily Closing Summary",
			"POS Cash Movement Report",
		),
	),
	(
		"Manufacturing Module Reports",
		(
			"BOM Stock Report",
			"Work Order Stock Report",
			"Open Work Orders",
			"Work Orders in Progress",
			"Completed Work Orders",
			"Work Order Summary",
			"Job Card Summary",
			"Production Analytics",
		),
	),
)

REPORT_SIDEBAR_GROUPS = REPORT_SIDEBAR_GROUPS + POS_REPORT_SIDEBAR_GROUPS


def _get_blocked_modules():
	blocked_modules = frappe.get_cached_doc("User", frappe.session.user).get_blocked_modules()
	return set(blocked_modules or [])


def extend_bootinfo(bootinfo):
	from retail.module_access import MODULE_ROLES, allowed
	bootinfo.retail_module_access = {module: allowed(module) for module in MODULE_ROLES}
	bootinfo.retail_blocked_modules = sorted(_get_blocked_modules())
	bootinfo.retail_workspace_modules = WORKSPACE_MODULES
	bootinfo.retail_workspace_sidebar_groups = WORKSPACE_SIDEBAR_GROUPS.copy()
	allowed_workspaces = _get_role_allowed_sidebar_workspaces()
	bootinfo.retail_allowed_sidebar_workspaces = (
		None if allowed_workspaces is None else sorted(allowed_workspaces)
	)
	# Keep home and inner-page workspace navigation consistent.
	# Frappe already calculated standard workspace permissions for this boot.
	# Apply Retail filtering to that result instead of repeating the full scan.
	if "allowed_workspaces" in bootinfo:
		bootinfo.allowed_workspaces = _filter_workspace_sidebar_items(
			{"pages": bootinfo.allowed_workspaces}
		).get("pages", [])
	else:
		bootinfo.allowed_workspaces = get_workspace_sidebar_items().get("pages", [])
	# Supply the same capability flags as the standard sidebar endpoint. The
	# browser can use this permission-filtered snapshot for its first mount.
	bootinfo.retail_workspace_sidebar_access = {
		"has_access": "Workspace Manager" in frappe.get_roles(),
		"has_create_access": frappe.has_permission(doctype="Workspace", ptype="create"),
	}
	bootinfo.retail_allowed_workspace_reports = (
		[page["route"][1] for page in get_permitted_report_sidebar_items() if page.get("is_report_link")]
		if any(page.get("title") == "Reports" for page in bootinfo.allowed_workspaces)
		else []
	)


def _get_role_allowed_sidebar_workspaces():
	from retail.sidebar_permissions import selection
	from retail.sidebar_registry import registry
	selected = selection()
	if selected is not None:
		return {group["workspace"] for group in registry() if group["id"] in selected}
	if frappe.session.user == "Administrator":
		return None

	roles = set(frappe.get_roles())
	if SYSTEM_MANAGER_ROLE in roles:
		return None

	allowed_workspaces = set()
	for role, workspaces in ROLE_SIDEBAR_WORKSPACES.items():
		if role in roles:
			allowed_workspaces.update(workspaces)

	allowed_workspaces.update(ALWAYS_VISIBLE_WORKSPACES)
	return allowed_workspaces


def _workspace_sidebar_is_allowed(page, blocked_modules, allowed_workspaces):
	title = page.get("title")
	if title in ALWAYS_VISIBLE_WORKSPACES:
		return True

	sidebar_group = page.get("sidebar_group") or WORKSPACE_SIDEBAR_GROUPS.get(title, title)
	from retail.module_access import MODULE_ROLES, allowed
	if sidebar_group in MODULE_ROLES and not allowed(sidebar_group):
		return False
	if allowed_workspaces is not None and sidebar_group not in allowed_workspaces:
		return False

	module = (
		page.get("module")
		if page.get("is_report_link")
		else WORKSPACE_MODULES.get(title) or page.get("module")
	)
	return not module or module not in blocked_modules


def get_permitted_report_sidebar_items():
	"""Build report navigation with distinct identities for repeated report labels."""
	from retail.module_access import target_module, allowed
	allowed_reports = get_allowed_reports(cache=True)
	blocked_modules = _get_blocked_modules()
	group_parents = {
		group: parent[0] if parent else "Reports"
		for group, _reports, *parent in REPORT_SIDEBAR_GROUPS
	}
	children_by_group = {}
	for group, reports, *_parent in REPORT_SIDEBAR_GROUPS:
		children = []
		for report_name in reports:
			module = target_module(report=report_name)
			if module and not allowed(module):
				continue
			if report_name not in allowed_reports:
				continue
			report = frappe.get_cached_doc("Report", report_name)
			if report.disabled or report.module in blocked_modules:
				continue
			if report.ref_doctype and not frappe.has_permission(report.ref_doctype, "read"):
				continue
			children.append(
				frappe._dict(
					name=f"retail-report-link-{frappe.scrub(group)}-{frappe.scrub(report_name)}",
					title=report_name,
					label=report_name,
					parent_page=group,
					sidebar_group="Reports",
					module=report.module,
					public=1,
					is_hidden=0,
					content="[]",
					is_report_link=1,
					route=["query-report", report_name],
				)
			)
		children_by_group[group] = children

	visible_groups = {group for group, children in children_by_group.items() if children}
	for group in list(visible_groups):
		parent = group_parents[group]
		while parent in group_parents:
			visible_groups.add(parent)
			parent = group_parents[parent]

	pages = []
	for group, _reports, *_parent in REPORT_SIDEBAR_GROUPS:
		if group not in visible_groups:
			continue
		pages.append(
			frappe._dict(
				name=group,
				title=group,
				label=group,
				parent_page=group_parents[group],
				sidebar_group="Reports",
				public=1,
				is_hidden=0,
				content="[]",
				is_report_group=1,
			)
		)
		pages.extend(children_by_group[group])
	return pages


class SidebarWorkspace(Workspace):
	"""Retail sidebar adapter; discovery lives only for one filtering operation.

	get_links mirrors Frappe's processing so every discovered item still passes
	is_item_allowed and _prepare_item. No framework globals are patched.
	"""

	def _prepare_item(self, item):
		# Only navigation presence is consumed by the sidebar filter. Loading
		# entire form metadata for its description makes cold boot very costly.
		# Keep the standard dependency/count/translation work and missing-target
		# behavior; leave full description enrichment to the opened workspace.
		if item.get("link_type") != "DocType":
			return super()._prepare_item(item)
		key = ("doctype_names",)
		if key not in self.sidebar_discovery:
			self.sidebar_discovery[key] = set(frappe.get_all("DocType", pluck="name"))
		if item.link_to not in self.sidebar_discovery[key]:
			raise frappe.DoesNotExistError
		prepared = super()._prepare_item(frappe._dict(item, link_type=None))
		prepared.link_type = item.link_type
		return prepared

	def _discover_custom_links(self, module):
		from copy import deepcopy

		if module not in self.sidebar_discovery:
			self.sidebar_discovery[module] = get_custom_reports_and_doctypes(module)
		# Workspace processing must never mutate another workspace's discovery.
		return deepcopy(self.sidebar_discovery[module])

	def get_links(self):
		cards = self.doc.get_link_groups()

		if not self.doc.hide_custom:
			cards = cards + self._discover_custom_links(self.doc.module)

		default_country = frappe.db.get_default("country")

		new_data = []
		for card in cards:
			new_items = []
			card = frappe._dict(card)

			links = card.get("links", [])

			for item in links:
				item = frappe._dict(item)

				# Condition: based on country
				if item.country and item.country != default_country:
					continue

				# Check if user is allowed to view
				if self.is_item_allowed(item.link_to, item.link_type):
					prepared_item = self._prepare_item(item)
					new_items.append(prepared_item)

			if new_items:
				if isinstance(card, frappe._dict):
					new_card = card.copy()
				else:
					new_card = card.as_dict().copy()
				new_card["links"] = new_items
				new_card["label"] = frappe._(new_card["label"])
				new_data.append(new_card)

		return new_data


def _workspace_has_permitted_content(page, discovery=None):
	try:
		workspace = SidebarWorkspace(page)
		workspace.sidebar_discovery = discovery if discovery is not None else {}
		workspace.build_workspace()
	except frappe.PermissionError:
		return False
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return False

	navigation_groups = (
		workspace.cards,
		workspace.shortcuts,
		workspace.onboardings,
		workspace.quick_lists,
	)

	return any(group.get("items") for group in navigation_groups if isinstance(group, dict))


def _has_report_permission(report_name):
	report = frappe.get_cached_doc("Report", report_name) if frappe.db.exists("Report", report_name) else None
	if not report or report.disabled:
		return False

	if report.ref_doctype and not frappe.has_permission(report.ref_doctype, "read"):
		return False

	if not report.roles:
		return True

	user_roles = set(frappe.get_roles())
	return any(role.role in user_roles for role in report.roles)


def _has_route_permission(permission_type, target):
	if permission_type == "doctype":
		return frappe.has_permission(target, "read")
	if permission_type == "page":
		if target in VAN_SALES_PAGES and _workspace_sidebar_is_allowed(
			{"title": "Van Sales", "module": "Van Sales"},
			_get_blocked_modules(),
			_get_role_allowed_sidebar_workspaces(),
		):
			return True
		return target in get_allowed_pages(cache=True)
	if permission_type == "report":
		return _has_report_permission(target)

	return False


def _workspace_has_route_permission(page):
	permissions = WORKSPACE_ROUTE_PERMISSIONS.get(page.get("title"))
	if not permissions:
		return False

	return all(_has_route_permission(permission_type, target) for permission_type, target in permissions)


def _normalize_sidebar_display(page):
	display_label = SIDEBAR_DISPLAY_LABELS.get(page.get("name")) or SIDEBAR_DISPLAY_LABELS.get(page.get("title"))
	if display_label:
		page = page.copy()
		page["label"] = display_label
	return page


@frappe.whitelist()
def get_workspace_sidebar_items():
	return _filter_workspace_sidebar_items(get_standard_workspace_sidebar_items())


def _filter_workspace_sidebar_items(sidebar):
	from copy import deepcopy

	# Keep the framework's original result intact for other boot consumers.
	sidebar = deepcopy(sidebar)

	pages = sidebar.get("pages") or []
	if not pages:
		return sidebar

	blocked_modules = _get_blocked_modules()
	allowed_workspaces = _get_role_allowed_sidebar_workspaces()
	pages = [frappe._dict(page, is_workspace_link=1) if page.get("title") == "Reports" else page for page in pages]
	reports_root = next((page for page in pages if page.get("title") == "Reports"), None)
	if reports_root and _workspace_sidebar_is_allowed(reports_root, blocked_modules, allowed_workspaces):
		report_pages = get_permitted_report_sidebar_items()
		report_names = {page["name"] for page in report_pages}
		pages = [page for page in pages if page.get("name") not in report_names] + report_pages

	def item_key(page):
		return page.get("name") or (page.get("parent_page"), page.get("title"))

	page_by_title = {page.get("title"): page for page in pages}
	children_by_parent = {}
	for page in pages:
		if page.get("parent_page"):
			children_by_parent.setdefault(page.get("parent_page"), []).append(page)

	module_allowed = {
		item_key(page): _workspace_sidebar_is_allowed(page, blocked_modules, allowed_workspaces) for page in pages
	}
	permitted_routes = {
		item_key(page): bool(page.get("is_workspace_link") or page.get("is_report_link")) or _workspace_has_route_permission(page)
		for page in pages
	}
	keep_cache = {}
	# Never retain discovery or permission decisions beyond this operation.
	discovery = {}

	def should_keep(page):
		title = page.get("title")
		name = page.get("name")
		label = page.get("label")
		key = item_key(page)
		if title in HIDDEN_SIDEBAR_WORKSPACES or name in HIDDEN_SIDEBAR_WORKSPACES or label in HIDDEN_SIDEBAR_WORKSPACES:
			return False
		if key in keep_cache:
			return keep_cache[key]

		keep = module_allowed.get(key, True) and (
			permitted_routes.get(key, False)
			# Build content only when route permission has not already established
			# visibility. Hidden/blocked pages never need content construction.
			or (
				not (page.get("is_report_group") or page.get("is_report_link"))
				and _workspace_has_permitted_content(page, discovery)
			)
			or any(should_keep(child) for child in children_by_parent.get(title, []))
		)
		keep_cache[key] = keep
		return keep

	sidebar["pages"] = []
	for page in pages:
		if (
			page.get("title") in HIDDEN_SIDEBAR_WORKSPACES
			or page.get("name") in HIDDEN_SIDEBAR_WORKSPACES
			or page.get("label") in HIDDEN_SIDEBAR_WORKSPACES
		):
			continue
		parent = page_by_title.get(page.get("parent_page")) if page.get("parent_page") else None
		if should_keep(page) and (not parent or should_keep(parent)):
			sidebar["pages"].append(_normalize_sidebar_display(page))

	unique_pages = {}
	for page in sidebar["pages"]:
		key = (page.get("parent_page") or "", page.get("title") or page.get("name"))
		unique_pages.setdefault(key, page)
	sidebar["pages"] = list(unique_pages.values())
	van_sales = next((page for page in sidebar["pages"] if page.get("name") == "Van Sales"), None)
	pos = next((page for page in sidebar["pages"] if page.get("name") == "POS"), None)
	if van_sales and pos:
		sidebar["pages"].remove(van_sales)
		sidebar["pages"].insert(sidebar["pages"].index(pos) + 1, van_sales)
	promotions = next((page for page in sidebar["pages"] if page.get("name") == "Promotions"), None)
	if promotions:
		sidebar["pages"].remove(promotions)
		settings_index = next((i for i, page in enumerate(sidebar["pages"]) if page.get("name") == "Settings"), len(sidebar["pages"]))
		sidebar["pages"].insert(settings_index, promotions)
		for doctype in ("Promo Price", "Buy X Get Y Promotion", "Gift Voucher Promotion", "Gift Voucher Ledger"):
			if frappe.has_permission(doctype, "read"):
				name = f"Promotions {doctype} Link"
				sidebar["pages"].append(frappe._dict(name=name, title=name, label=doctype, parent_page="Promotions", public=1, is_hidden=0, module="Retail-app"))


		loyalty_links = (
			("Loyalty Program", "Loyalty Program", "List"),
			("Loyalty Program List", "Loyalty Program", "List"),
			("Loyalty Program Report", "Loyalty Program", "Report"),
			("Loyalty Point Entry", "Loyalty Point Entry", "List"),
			("Loyalty Point Entry Report", "Loyalty Point Entry", "Report"),
		)
		if frappe.has_permission("Loyalty Program", "read"):
			for label, doctype, view in loyalty_links:
				if not frappe.has_permission(doctype, "read"):
					continue
				if view == "Report" and not frappe.has_permission(doctype, "report"):
					continue
				name = f"Promotions {label} Link"
				sidebar["pages"].append(frappe._dict(
					name=name, title=name, label=label,
					parent_page="Promotions" if label == "Loyalty Program" else "Promotions Loyalty Program Link",
					public=1, is_hidden=0, module="Accounts",
					route=["List", doctype, view],
				))

	from retail.sidebar_permissions import filter_sidebar
	from retail.sidebar_registry import normalize_sidebar
	sidebar["pages"] = normalize_sidebar(filter_sidebar(sidebar["pages"]))
	return sidebar

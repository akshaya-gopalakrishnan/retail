import frappe
from frappe.desk.desktop import Workspace
from frappe.desk.desktop import get_workspace_sidebar_items as get_standard_workspace_sidebar_items


WORKSPACE_MODULES = {
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
	"Promo Price": "Selling",
	"Buy X Get Y Promotion": "Selling",
	"Gift Voucher Promotion": "Selling",
	"Gift Voucher Ledger": "Selling",
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
	bootinfo.retail_blocked_modules = sorted(_get_blocked_modules())
	bootinfo.retail_workspace_modules = WORKSPACE_MODULES


def _report_is_allowed(report_name, report_by_name, user_roles):
	report = report_by_name.get(report_name)
	if not report or report.disabled:
		return False

	if frappe.session.user == "Administrator" or "System Manager" in user_roles:
		return True

	report_roles = {role.role for role in getattr(report, "roles", []) if role.role}
	if report_roles and not report_roles.intersection(user_roles):
		return False

	try:
		return frappe.has_permission("Report", "read", doc=report)
	except Exception:
		return False


def get_permitted_report_sidebar_items():
	report_names = sorted({report for _group, reports, *_parent in REPORT_SIDEBAR_GROUPS for report in reports})
	existing_report_names = set(frappe.get_all("Report", filters={"name": ("in", report_names)}, pluck="name"))
	report_by_name = {report_name: frappe.get_doc("Report", report_name) for report_name in existing_report_names}

	user_roles = set(frappe.get_roles(frappe.session.user))
	pages = []
	for group_config in REPORT_SIDEBAR_GROUPS:
		group, reports, *parent = group_config
		children = []
		for report_name in reports:
			if _report_is_allowed(report_name, report_by_name, user_roles):
				children.append(
					{
						"name": report_name,
						"title": report_name,
						"label": report_name,
						"parent_page": group,
						"public": 1,
						"is_hidden": 0,
						"is_report_link": 1,
						"route": ["query-report", report_name],
					}
				)

		if not children:
			continue

		pages.append(
			{
						"name": group,
						"title": group,
						"label": group,
						"parent_page": parent[0] if parent else "Reports",
						"public": 1,
						"is_hidden": 0,
						"is_report_group": 1,
			}
		)
		pages.extend(children)

	return pages


def get_permitted_promotion_sidebar_items():
	items = []
	for doctype in ("Promo Price", "Buy X Get Y Promotion", "Gift Voucher Promotion", "Gift Voucher Ledger"):
		if frappe.has_permission(doctype, "read"):
			items.append(
				{
					"name": f"retail-{frappe.scrub(doctype)}-list-link",
					"title": doctype,
					"label": doctype,
					"parent_page": "Sales",
					"public": 1,
					"is_hidden": 0,
					"content": "[]",
					"route": ["List", doctype],
				}
			)
	return items


def _workspace_module_is_allowed(page, blocked_modules):
	module = WORKSPACE_MODULES.get(page.get("title")) or page.get("module")
	return not module or module not in blocked_modules


def _workspace_has_permitted_content(page):
	try:
		workspace = Workspace(page)
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


@frappe.whitelist()
def get_workspace_sidebar_items():
	sidebar = get_standard_workspace_sidebar_items()

	def append_report_sidebar_items():
		if not any(page.get("title") == "Reports" for page in sidebar.get("pages") or []):
			return
		existing_titles = {page.get("title") for page in sidebar.get("pages") or []}
		for page in get_permitted_report_sidebar_items():
			if page.get("title") not in existing_titles:
				sidebar.setdefault("pages", []).append(page)
				existing_titles.add(page.get("title"))

	def append_promotion_sidebar_items():
		if not any(page.get("title") == "Sales" for page in sidebar.get("pages") or []):
			return
		existing_titles = {page.get("title") for page in sidebar.get("pages") or []}
		for page in get_permitted_promotion_sidebar_items():
			if page.get("title") not in existing_titles:
				sidebar.setdefault("pages", []).append(page)
				existing_titles.add(page.get("title"))

	if sidebar.get("has_access"):
		append_promotion_sidebar_items()
		append_report_sidebar_items()
		return sidebar

	pages = sidebar.get("pages") or []
	if not pages:
		return sidebar

	blocked_modules = _get_blocked_modules()
	page_by_title = {page.get("title"): page for page in pages}
	children_by_parent = {}
	for page in pages:
		if page.get("parent_page"):
			children_by_parent.setdefault(page.get("parent_page"), []).append(page)

	module_allowed = {
		page.get("title"): _workspace_module_is_allowed(page, blocked_modules) for page in pages
	}
	permitted_content = {page.get("title"): _workspace_has_permitted_content(page) for page in pages}
	keep_cache = {}

	def should_keep(page):
		title = page.get("title")
		if title in keep_cache:
			return keep_cache[title]

		keep = module_allowed.get(title, True) and (
			permitted_content.get(title, False)
			or any(should_keep(child) for child in children_by_parent.get(title, []))
		)
		keep_cache[title] = keep
		return keep

	sidebar["pages"] = []
	for page in pages:
		parent = page_by_title.get(page.get("parent_page")) if page.get("parent_page") else None
		if should_keep(page) and (not parent or should_keep(parent)):
			sidebar["pages"].append(page)

	append_report_sidebar_items()
	append_promotion_sidebar_items()

	return sidebar

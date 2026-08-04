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


def _get_blocked_modules():
	blocked_modules = frappe.get_cached_doc("User", frappe.session.user).get_blocked_modules()
	return set(blocked_modules or [])


def extend_bootinfo(bootinfo):
	bootinfo.retail_blocked_modules = sorted(_get_blocked_modules())
	bootinfo.retail_workspace_modules = WORKSPACE_MODULES


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

	if sidebar.get("has_access"):
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

	return sidebar

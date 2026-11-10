"""One-time accounting defaults for companies created after Retail installation.

Never backfill existing companies or change submitted transactions. Company hooks
run after ERPNext creates the chart; POS hooks only fill new profiles' blank fields.
"""

import frappe
from frappe import _


VERSION_FIELD = "custom_retail_accounting_defaults_version"
VERSION = 1

# field: (fallback name, root, type, preferred existing account names)
DEFAULTS = {
	"default_income_account": ("Retail Sales", "Income", "Income Account", ("Sales", "Sales Account", "Retail Sales", "Pos Sales", "Shop Sales")),
	"default_expense_account": ("Cost of Goods Sold", "Expense", "Cost of Goods Sold", ("Cost of Goods Sold",)),
	"default_cash_account": ("Cash", "Asset", "Cash", ("Main Safe", "Cash", "Cash In Hand")),
	"default_bank_account": ("Bank", "Asset", "Bank", ("Bank", "Bank Account")),
	"default_receivable_account": ("Trade Receivables", "Asset", "Receivable", ("Debtors", "Accounts Receivable", "Trade Receivable", "Trade Receivables")),
	"default_payable_account": ("Trade Payables", "Liability", "Payable", ("Creditors", "Accounts Payable", "Trade Payable", "Trade Payables")),
	"default_inventory_account": ("Stock In Hand", "Asset", "Stock", ("Stock In Hand",)),
	"stock_received_but_not_billed": ("Stock Received But Not Billed", "Liability", "Stock Received But Not Billed", ("Stock Received But Not Billed",)),
	"stock_adjustment_account": ("Stock Adjustment", "Expense", "Stock Adjustment", ("Stock Adjustment",)),
	"expenses_included_in_valuation": ("Expenses Included In Valuation", "Expense", "Expenses Included In Valuation", ("Expenses Included In Valuation",)),
	"round_off_account": ("Round Off", "Expense", "Round Off", ("Round Off",)),
	"write_off_account": ("Write Off", "Expense", "", ("Write Off", "Write Off Receivables & Payables")),
	"exchange_gain_loss_account": ("Exchange Gain/Loss", "Expense", "", ("Exchange Gain/Loss",)),
}

# Received card/cheque/draft instruments remain separate from the actual bank.
PAYMENT_ACCOUNT_SPECS = {
	"Card": ("Manual Visa & Master Cards", "Asset", "Bank", ("Manual Visa & Master Cards",)),
	"Credit Card": ("Visa & Master Credit Cards", "Asset", "Bank", ("Visa & Master Credit Cards",)),
	"Cheque": ("Post Dated Cheques Received", "Asset", "Bank", ("Post Dated Cheques Received",)),
	"Bank Draft": ("Bank Drafts Received", "Asset", "Bank", ("Bank Drafts Received",)),
}


def install():
	"""Schema only: upgrading a site must not remap its existing companies."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({"Company": [{
		"fieldname": VERSION_FIELD,
		"label": "Retail Accounting Defaults Version",
		"fieldtype": "Int",
		"default": "0",
		"read_only": 1,
		"hidden": 1,
		"no_copy": 1,
		"insert_after": "default_income_account",
	}]})


def remember_company_choices(doc, method=None):
	# ERPNext fills accounts in its own on_update. Capture the caller's choices
	# beforehand so its arbitrary Income Account lookup is not mistaken for one.
	doc.flags.retail_initial_account_choices = {field: doc.get(field) for field in DEFAULTS}


def initialize_company(doc, method=None):
	choices = doc.flags.get("retail_initial_account_choices")
	if choices is None or doc.get(VERSION_FIELD) or doc.is_group:
		return
	if frappe.local.flags.get("ignore_chart_of_accounts"):
		return
	if not doc.meta.has_field(VERSION_FIELD):
		return
	if not frappe.db.exists("Account", {"company": doc.name}):
		return

	native_cash_default = doc.default_cash_account
	for field, spec in DEFAULTS.items():
		if choices.get(field):
			if doc.get(field) != choices[field]:
				doc.db_set(field, choices[field], update_modified=False)
			continue
		current = doc.get(field)
		# Explicit choices inherited from a copied chart are site-owned too.
		if doc.create_chart_of_accounts_based_on == "Existing Company" and current:
			continue
		if field == "default_cash_account":
			main_safe = frappe.db.get_value("Account", {"company": doc.name, "account_name": "Main Safe"}, "name")
			if _valid_account(main_safe, doc, spec):
				doc.db_set(field, main_safe, update_modified=False)
				continue
		retain_native = field != "default_income_account" and _valid_account(current, doc, spec)
		if field == "default_bank_account" and retain_native:
			# Core selects the first Bank-type leaf, which can be a card/cheque
			# clearing account in imported charts. It is not a wire-transfer bank.
			label = frappe.db.get_value("Account", current, "account_name")
			collection_names = {s[0].casefold() for s in PAYMENT_ACCOUNT_SPECS.values()}
			collection_names.add("card clearing")
			retain_native = label.casefold() not in collection_names
		if retain_native:
			continue
		account = _resolve_account(doc, spec)
		if account != current:
			doc.db_set(field, account, update_modified=False)

	_initialize_payment_modes(doc, native_cash_default=native_cash_default)
	if not doc.round_off_cost_center and doc.cost_center:
		doc.db_set("round_off_cost_center", doc.cost_center, update_modified=False)
	doc.db_set(VERSION_FIELD, VERSION, update_modified=False)
	doc.flags.pop("retail_initial_account_choices", None)


def _account_types(spec):
	# The native UAE chart classifies received post-dated cheques as receivables.
	# Accept that existing ledger without retyping it or changing other tenders.
	if spec[0] == "Post Dated Cheques Received" and spec[2] == "Bank":
		return ("Bank", "Receivable")
	return ("", "Income Account") if spec[2] == "Income Account" else (spec[2],)


def _valid_account(name, company, spec):
	if not name:
		return False
	account = frappe.db.get_value("Account", name,
		["company", "root_type", "account_type", "account_currency", "is_group", "disabled"], as_dict=True)
	valid_types = _account_types(spec)
	return bool(account and account.company == company.name and account.root_type == spec[1]
		and (account.account_type or "") in valid_types and not account.is_group and not account.disabled
		and account.account_currency == company.default_currency)


def _resolve_account(company, spec):
	label, root, account_type, preferred_names = spec
	filters = {"company": company.name, "root_type": root, "is_group": 0,
		"disabled": 0, "account_currency": company.default_currency}
	if len(_account_types(spec)) > 1:
		filters["account_type"] = ["in", list(_account_types(spec))]
	elif account_type:
		filters["account_type"] = account_type
	accounts = frappe.get_all("Account", filters=filters, fields=["name", "account_name"], order_by="name")
	for preferred in preferred_names:
		matches = [a.name for a in accounts if a.account_name.casefold() == preferred.casefold()]
		if len(matches) == 1:
			return matches[0]
	# Do not guess between multiple cash/bank/receivable accounts or treat any
	# arbitrary Income Account as retail sales. Make a clearly named fallback.
	return _create_account(company, label, root, account_type)


def _create_account(company, label, root, account_type):
	existing = frappe.db.get_value("Account", {"company": company.name, "account_name": label}, "name")
	if existing:
		if _valid_account(existing, company, (label, root, account_type, ())):
			return existing
		frappe.throw(_("Account {0} already exists with incompatible properties. Select your own company default before saving.").format(existing))
	groups = frappe.get_all("Account", filters={"company": company.name, "root_type": root,
		"is_group": 1, "disabled": 0}, fields=["name", "account_type", "lft"], order_by="lft")
	if not groups:
		frappe.throw(_("A {0} account group is required for company {1}.").format(root, company.name))
	typed_groups = [g for g in groups if account_type and g.account_type == account_type]
	parent = typed_groups[0].name if len(typed_groups) == 1 else groups[0].name
	return frappe.get_doc({"doctype": "Account", "company": company.name,
		"account_name": label, "parent_account": parent, "is_group": 0,
		"account_type": account_type, "account_currency": company.default_currency,
		"include_in_gross": int(account_type in ("Income Account", "Cost of Goods Sold")),
	}).insert(ignore_permissions=True).name


def _initialize_payment_modes(company, native_cash_default=None):
	_ensure_payment_mode(company, "Cash", "Cash", account=company.default_cash_account,
		replace_native_account=native_cash_default)
	for name, spec in PAYMENT_ACCOUNT_SPECS.items():
		_ensure_payment_mode(company, name, "Bank", spec=spec)
	_ensure_payment_mode(company, "Wire Transfer", "Bank", account=company.default_bank_account)


def _ensure_payment_mode(company, name, payment_type, account=None, spec=None, replace_native_account=None):
	if frappe.db.exists("Mode of Payment", name):
		mode = frappe.get_doc("Mode of Payment", name, for_update=True)
		# Site-owned modes may have a different purpose or be disabled.
		if mode.type != payment_type or not mode.enabled:
			return
	else:
		mode = frappe.new_doc("Mode of Payment")
		mode.mode_of_payment = name
		mode.type = payment_type
		mode.enabled = 1
	rows = [r for r in mode.accounts if r.company == company.name]
	if rows and rows[0].default_account:
		if not replace_native_account or rows[0].default_account != replace_native_account:
			return
		if rows[0].default_account == account:
			return
	# Resolve only missing mappings, so a site-selected account never creates an
	# unnecessary fallback ledger (or fails on an unused conflicting account name).
	account = account or _resolve_account(company, spec)
	if rows:
		rows[0].default_account = account
	else:
		mode.append("accounts", {"company": company.name, "default_account": account})
	mode.save(ignore_permissions=True)


def set_pos_profile_defaults(doc, method=None):
	"""New profiles inherit company defaults; later edits remain authoritative."""
	if not doc.is_new() or not doc.company:
		return
	company = frappe.get_cached_doc("Company", doc.company)
	if not company.get(VERSION_FIELD):
		return
	for field, company_field in {
		"income_account": "default_income_account",
		"expense_account": "default_expense_account",
		"write_off_account": "write_off_account",
		"account_for_change_amount": "default_cash_account",
		"cost_center": "cost_center",
		"write_off_cost_center": "cost_center",
	}.items():
		if not doc.get(field):
			doc.set(field, company.get(company_field))

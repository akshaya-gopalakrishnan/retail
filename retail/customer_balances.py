"""Read-only Customer List amounts from ERPNext's open payment references."""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate

from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport
from erpnext.accounts.utils import get_currency_precision


@frappe.whitelist()
def get_customer_credit_balances(customers, company=None):
	"""Return display amounts in company currency; never persist accounting balances."""
	frappe.has_permission("Customer", "read", throw=True)
	frappe.has_permission("Payment Ledger Entry", "read", throw=True)
	if isinstance(customers, str):
		customers = frappe.parse_json(customers)
	if not isinstance(customers, list) or any(not isinstance(name, str) for name in customers):
		frappe.throw(_("Customers must be a list of customer names."))
	if len(customers) > 500:
		frappe.throw(_("Request at most 500 customers at a time."))

	company = company or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Set a default Company to view customer credit balances."))
	company_doc = frappe.get_doc("Company", company)
	company_doc.check_permission("read")
	response = {
		"company": company,
		"currency": company_doc.default_currency,
		"as_of": str(now_datetime()),
		"data": [],
	}
	if not customers:
		return response
	# get_list preserves Customer user permissions and the project's van partition.
	parties = frappe.get_list(
		"Customer", filters={"name": ["in", customers]},
		fields=["name", "customer_name", "customer_group", "territory", "customer_primary_contact"],
		limit_page_length=0,
	)
	if not parties:
		return response
	names = [row.name for row in parties]
	limits = _credit_limits(parties, company_doc)
	balances = {
		name: {"customer": name, "credit_limit": limits[name],
			"outstanding_amount": 0.0, "unused_credit_note_amount": 0.0}
		for name in names
	}
	returns = set(frappe.get_all(
		"Sales Invoice",
		filters={"company": company, "customer": ["in", names], "docstatus": 1, "is_return": 1},
		pluck="name",
	))
	# Use the same report and signed customer subtotal as Accounts Receivable.
	# ERPNext handles allocations, advances, returns, cancellations and FX.
	report = _CustomerReceivables({
		"company": company, "party_type": "Customer", "party": names,
		"report_date": nowdate(), "group_by_party": 1,
	})
	report.list_parties = {row.name: row for row in parties}
	rows = report.run({
		"account_type": "Receivable",
		"naming_by": ["Selling Settings", "cust_master_name"],
	})[1]
	for name, balance in balances.items():
		balance["outstanding_amount"] = report.total_row_map.get(name, {}).get("outstanding", 0.0)
	_set_unused_credit_notes(balances, rows, returns)
	precision = get_currency_precision() or 2
	for balance in balances.values():
		_finalize(balance, precision)
	response["data"] = list(balances.values())
	from retail.pos_settlements import add_customer_summaries
	add_customer_summaries(response["data"], company, "customer")
	return response


def _credit_limits(parties, company):
	"""Batch the configuration fallback used by ERPNext Customer.get_credit_limit."""
	names = [row.name for row in parties]
	groups = list({row.customer_group for row in parties if row.customer_group})
	customer_limits = {row.parent: row.credit_limit for row in frappe.get_all(
		"Customer Credit Limit",
		filters={"parenttype": "Customer", "parent": ["in", names], "company": company.name},
		fields=["parent", "credit_limit"],
	)}
	group_limits = {}
	if groups:
		group_limits = {row.parent: row.credit_limit for row in frappe.get_all(
			"Customer Credit Limit",
			filters={"parenttype": "Customer Group", "parent": ["in", groups], "company": company.name,
				"bypass_credit_limit_check": 0},
			fields=["parent", "credit_limit"],
		)}
	return {
		row.name: flt(customer_limits.get(row.name) or group_limits.get(row.customer_group) or company.credit_limit)
		for row in parties
	}


class _CustomerReceivables(ReceivablePayableReport):
	"""Only batch party labels; all accounting remains in ERPNext's report."""

	def get_party_details(self, party):
		return self.list_parties.get(party, {})


def _set_unused_credit_notes(balances, rows, returns):
	"""Informational subset of native open rows; never deduct it from net receivable."""
	for row in rows:
		balance = balances.get(row.get("party"))
		if balance is None or row.get("voucher_type") != "Sales Invoice":
			continue
		amount = flt(row.get("outstanding"))
		if amount < 0 and row.get("voucher_no") in returns:
			balance["unused_credit_note_amount"] -= amount


def _finalize(balance, precision):
	for field in ("credit_limit", "outstanding_amount", "unused_credit_note_amount"):
		balance[field] = flt(balance[field], precision)
	# Outstanding is already the NET native receivable, including all open credits.
	# Retain response aliases for consumers of the original display endpoint.
	balance["net_balance"] = balance["outstanding_amount"]
	balance["remaining_credit_limit"] = flt(balance["credit_limit"] - balance["outstanding_amount"], precision)
	balance["available_credit_including_credit_notes"] = balance["remaining_credit_limit"]

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime


class POSBranchDayClosing(Document):
	def validate(self):
		if not self.business_date:
			frappe.throw(_("Business Date is required."))
		if not self.branch:
			frappe.throw(_("Branch is required."))
		self.validate_unique_branch_date()
		self.manager_user = self.manager_user or frappe.session.user
		self.refresh_summaries()

	def validate_unique_branch_date(self):
		duplicates = frappe.get_all(
			"POS Branch Day Closing",
			filters={
				"branch": self.branch,
				"business_date": self.business_date,
				"docstatus": ["!=", 2],
				"name": ["!=", self.name],
			},
			fields=["name", "docstatus"],
			order_by="docstatus desc, creation asc",
			limit_page_length=1,
		)
		if duplicates:
			duplicate = duplicates[0]
			status = _("submitted") if duplicate.docstatus == 1 else _("draft")
			frappe.throw(
				_("Day closing already exists for {0} on {1}: {2} ({3}). Open that document instead.").format(
					self.branch, self.business_date, frappe.bold(duplicate.name), status
				)
			)

	def before_submit(self):
		self.refresh_summaries()
		self.validate_close_ready()

	def before_cancel(self):
		if not self.cancel_reason:
			frappe.throw(_("Cancel / Reopen Reason is required before cancelling day closing."))

	def validate_close_ready(self):
		if self.open_shift_count or self.active_counter_session_count:
			frappe.throw(_("Cannot close the day while cashier shifts or counter sessions are still open."))
		if not self.cashier_summaries:
			frappe.throw(_("No cashier shifts found for this branch and business date."))
		self.closed_at = self.closed_at or now_datetime()

	def refresh_summaries(self):
		shifts = _get_cashier_shifts(self.branch, self.business_date)
		sales_by_shift = _get_sales_by_shift([row.name for row in shifts])
		self.set("cashier_summaries", [])
		self.set("counter_summaries", [])

		open_shift_count = 0
		total_sales = total_expected = total_counted = total_variance = total_invoices = 0
		total_cash_in = total_cash_out = 0
		for shift in shifts:
			sales = sales_by_shift.get(shift.name, {})
			if shift.status != "Closed":
				open_shift_count += 1
			cash_in_amount = flt(shift.get("cash_in_amount"))
			cash_out_amount = flt(shift.get("cash_out_amount"))
			expected_cash = flt(shift.expected_cash)
			closing_amount = flt(shift.closing_amount)
			variance = flt(shift.variance)
			total_sales += flt(sales.get("sales_total"))
			total_cash_in += cash_in_amount
			total_cash_out += cash_out_amount
			total_expected += expected_cash
			total_counted += closing_amount
			total_variance += variance
			total_invoices += int(sales.get("invoice_count") or 0)
			self.append(
				"cashier_summaries",
				{
					"cashier_shift": shift.name,
					"cashier_employee": shift.cashier_employee,
					"cashier_name": shift.cashier_name,
					"status": shift.status,
					"opening_time": shift.opening_time,
					"closing_time": shift.closing_time,
					"opening_amount": shift.opening_amount,
					"cash_in_amount": cash_in_amount,
					"cash_out_amount": cash_out_amount,
					"expected_cash": expected_cash,
					"closing_amount": closing_amount,
					"variance": variance,
					"invoice_count": int(sales.get("invoice_count") or 0),
					"sales_total": flt(sales.get("sales_total")),
				},
			)

		counter_rows = _get_counter_summary(self.branch, [row.name for row in shifts])
		for row in counter_rows:
			self.append("counter_summaries", row)

		self.total_cashier_shifts = len(shifts)
		self.open_shift_count = open_shift_count
		self.closed_shift_count = len(shifts) - open_shift_count
		self.active_counter_session_count = frappe.db.count(
			"POS Counter Session",
			{"branch": self.branch, "status": "Active"},
		)
		self.total_invoice_count = total_invoices
		self.total_sales = total_sales
		self.total_cash_in = total_cash_in
		self.total_cash_out = total_cash_out
		self.total_expected_cash = total_expected
		self.total_closing_cash = total_counted
		self.total_variance = total_variance


def _get_cashier_shifts(branch, business_date):
	return frappe.get_all(
		"POS Cashier Shift",
		filters={
			"branch": branch,
			"opening_time": ["between", [f"{getdate(business_date)} 00:00:00", f"{getdate(business_date)} 23:59:59"]],
		},
		fields=[
			"name",
			"cashier_employee",
			"cashier_name",
			"status",
			"opening_time",
			"closing_time",
			"opening_amount",
			"cash_in_amount",
			"cash_out_amount",
			"expected_cash",
			"closing_amount",
			"variance",
		],
		order_by="opening_time asc",
	)


def _get_sales_by_shift(cashier_shifts):
	if not cashier_shifts:
		return {}
	rows = frappe.db.sql(
		"""
		select pos_cashier_shift, count(*) as invoice_count, sum(grand_total) as sales_total
		from `tabPOS Invoice`
		where docstatus = 1 and pos_cashier_shift in %(cashier_shifts)s
		group by pos_cashier_shift
		""",
		{"cashier_shifts": tuple(cashier_shifts)},
		as_dict=True,
	)
	return {row.pos_cashier_shift: row for row in rows}


def _get_counter_summary(branch, cashier_shifts):
	if not cashier_shifts:
		return []
	counter_rows = frappe.get_all(
		"POS Counter Session",
		filters={"branch": branch, "cashier_shift": ["in", cashier_shifts]},
		fields=["counter", "counter_code", "count(name) as session_count"],
		group_by="counter, counter_code",
	)
	sales_rows = frappe.db.sql(
		"""
		select pos_counter, count(*) as invoice_count, sum(grand_total) as sales_total
		from `tabPOS Invoice`
		where docstatus = 1 and pos_cashier_shift in %(cashier_shifts)s
		group by pos_counter
		""",
		{"cashier_shifts": tuple(cashier_shifts)},
		as_dict=True,
	)
	sales_by_counter = {row.pos_counter: row for row in sales_rows}
	amount_rows = frappe.db.sql(
		"""
		select x.counter, sum(c.expected_cash) as expected_cash, sum(c.closing_amount) as closing_amount, sum(c.variance) as variance
		from (
			select distinct counter, cashier_shift
			from `tabPOS Counter Session`
			where branch = %(branch)s and cashier_shift in %(cashier_shifts)s
		) x
		inner join `tabPOS Cashier Shift` c on c.name = x.cashier_shift
		group by x.counter
		""",
		{"branch": branch, "cashier_shifts": tuple(cashier_shifts)},
		as_dict=True,
	)
	amounts_by_counter = {row.counter: row for row in amount_rows}
	result = []
	for row in counter_rows:
		sales = sales_by_counter.get(row.counter, {})
		amounts = amounts_by_counter.get(row.counter, {})
		result.append(
			{
				"counter": row.counter,
				"counter_code": row.counter_code,
				"session_count": row.session_count,
				"invoice_count": int(sales.get("invoice_count") or 0),
				"sales_total": flt(sales.get("sales_total")),
				"expected_cash": flt(amounts.get("expected_cash")),
				"closing_amount": flt(amounts.get("closing_amount")),
				"variance": flt(amounts.get("variance")),
			}
		)
	return result


@frappe.whitelist()
def make_day_closing(branch, business_date):
	existing = frappe.get_all(
		"POS Branch Day Closing",
		filters={"branch": branch, "business_date": business_date, "docstatus": ["!=", 2]},
		fields=["name", "docstatus"],
		order_by="docstatus desc, creation asc",
		limit_page_length=1,
	)
	doc = frappe.get_doc("POS Branch Day Closing", existing[0].name) if existing else frappe.new_doc("POS Branch Day Closing")
	if doc.docstatus == 1:
		return doc.as_dict()

	doc.branch = branch
	doc.business_date = business_date
	doc.manager_user = frappe.session.user
	doc.refresh_summaries()
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc.as_dict()


@frappe.whitelist()
def submit_day_closing(branch, business_date):
	doc = make_day_closing(branch, business_date)
	closing = frappe.get_doc("POS Branch Day Closing", doc.name)
	if closing.docstatus == 0:
		closing.submit()
	return closing.as_dict()


@frappe.whitelist()
def cancel_day_closing(branch, business_date, reason):
	if not reason:
		frappe.throw(_("Reason is required to cancel day closing."))
	name = frappe.db.get_value(
		"POS Branch Day Closing",
		{"branch": branch, "business_date": business_date, "docstatus": 1},
		"name",
		order_by="creation asc",
	)
	if not name:
		frappe.throw(_("No submitted day closing found for {0} on {1}.").format(branch, business_date))
	doc = frappe.get_doc("POS Branch Day Closing", name)
	doc.cancel_reason = reason
	doc.flags.ignore_validate_update_after_submit = True
	doc.save(ignore_permissions=True)
	doc.cancel()
	return doc.as_dict()

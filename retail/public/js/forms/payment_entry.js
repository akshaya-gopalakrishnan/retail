(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Payment Entry", {
		onload(frm) {
			applyVanInvoiceContext(frm);
		},
		refresh(frm) {
			applyVanInvoiceContext(frm);
			updatePartyReviewButtons(frm);
		},
		payment_type(frm) {
			updatePartyReviewButtons(frm);
		},
		party_type(frm) {
			updatePartyReviewButtons(frm);
		},
		party(frm) {
			updatePartyReviewButtons(frm);
		},
		company(frm) {
			updatePartyReviewButtons(frm);
		},
		custom_van_session(frm) {
			fetchVanSessionDetails(frm);
		},
	});

	function canReviewCustomer(frm) {
		return frm.doc.payment_type === "Receive" && frm.doc.party_type === "Customer" &&
			Boolean(frm.doc.party && frm.doc.company);
	}

	function updatePartyReviewButtons(frm) {
		updateSupplierStockButton(frm);
		const label = __("Customer Payment Review");
		frm.remove_custom_button(label);
		const review = frm.__retail_customer_credit_review;
		if (review && (!canReviewCustomer(frm) || review.customer !== frm.doc.party || review.company !== frm.doc.company)) {
			review.request++;
			review.dialog.hide();
		}
		if (canReviewCustomer(frm)) frm.add_custom_button(label, () => openCustomerCreditReview(frm));
	}

	function openCustomerCreditReview(frm) {
		if (!canReviewCustomer(frm)) return;
		frm.__retail_customer_credit_review?.dialog.hide();
		const state = { customer: frm.doc.party, company: frm.doc.company, request: 0 };
		const dialog = state.dialog = new frappe.ui.Dialog({
			title: __("Customer Payment Review"),
			size: "extra-large",
			fields: [
				{ fieldname: "months", fieldtype: "Select", label: __("Review Period (Months)"),
					options: "3\n6\n12\n24", default: "12", onchange: () => state.ready && load() },
				{ fieldname: "review", fieldtype: "HTML" },
			],
			primary_action_label: __("Close"),
			primary_action: () => dialog.hide(),
			secondary_action_label: __("Refresh"),
			secondary_action: () => load(),
		});
		frm.__retail_customer_credit_review = state;
		state.ready = true;
		dialog.show();
		load();

		async function load() {
			const request = ++state.request;
			const wrapper = dialog.fields_dict.review.$wrapper;
			wrapper.html(`<p class="text-muted">${__("Loading customer payment history…")}</p>`);
			try {
				const result = await frappe.call({
					method: "retail.customer_credit_review.get_review",
					args: { customer: state.customer, company: state.company, months: dialog.get_value("months") },
				});
				if (request !== state.request || frm.__retail_customer_credit_review !== state) return;
				wrapper.html(renderCustomerCreditReview(result.message));
			} catch (_error) {
				if (request !== state.request || frm.__retail_customer_credit_review !== state) return;
				wrapper.html(`<p class="text-danger">${__("Payment review unavailable. Check your accounting permissions or try Refresh.")}</p>`);
			}
		}
	}

	const reviewEscape = value => frappe.utils.escape_html(String(value ?? ""));
	const reviewNumber = value => value == null ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
	const reviewMoney = (value, currency) => value == null ? "—" : `${reviewEscape(currency)} ${reviewNumber(value)}`;
	const reviewDate = value => value ? reviewEscape(frappe.datetime.str_to_user(value)) : "—";
	const reviewLink = (doctype, name) => `<a href="/app/${reviewEscape(frappe.router.slug(doctype))}/${encodeURIComponent(name)}" target="_blank" rel="noopener">${reviewEscape(name)}</a>`;

	function reviewTable(headers, rows) {
		return `<div class="table-responsive"><table class="table table-sm table-bordered"><thead><tr>${headers.map(label => `<th>${reviewEscape(__(label))}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${headers.length}" class="text-muted">${__("No records in this period.")}</td></tr>`}</tbody></table></div>`;
	}

	function renderCustomerCreditReview(data) {
		const s = data.snapshot, stats = data.statistics;
		const money = value => reviewMoney(value, data.currency);
		let html = `<p><strong>${reviewEscape(data.customer)} · ${reviewEscape(data.customer_name)}</strong><br>${reviewEscape(data.company)} · ${__("As of")} ${reviewDate(data.as_of)}</p>`;
		html += reviewTable(["Current Credit Position", "Amount"], [
			[__("Effective credit limit"), s.credit_limit > 0 ? money(s.credit_limit) : __("No positive limit configured")],
			[__("Payment terms"), reviewEscape(data.payment_terms || "—")],
			[__("Net receivable balance"), money(s.outstanding)],
			[__("Open order and delivery commitments"), money(s.commitments)],
			[__("Credit exposure"), money(s.credit_exposure)],
			[__("Available credit"), money(s.available_credit)],
			[__("Overdue amount before unallocated credits"), `<strong>${money(s.overdue)}</strong>`],
			[__("Oldest overdue invoice / instalment"), `${reviewNumber(s.oldest_overdue_days)} ${__("days")}`],
			[__("Unallocated receipts already included in net receivable"), money(s.unallocated_receipts)],
			[__("Unused credit notes already included in net receivable"), money(s.unused_credit_notes)],
		]);
		if (s.commitments == null) html += `<p class="text-muted small">${__("Available credit requires access to open sales orders and deliveries.")}</p>`;
		if (s.sales_order_bypass) html += `<p class="text-muted small">${__("Sales Orders are excluded from exposure by this customer's existing credit setting.")}</p>`;
		if (s.ageing_warning) html += `<p class="text-warning small">${__("Instalment ageing needs reconciliation. Overdue amounts below use invoice due dates; review the invoice schedules before judging delays.")}</p>`;
		html += reviewTable(["Overdue Age", `Amount (${data.currency})`], [
			[__("1–30 days"), money(s.ageing["1_30"])], [__("31–60 days"), money(s.ageing["31_60"])],
			[__("61–90 days"), money(s.ageing["61_90"])], [__("Over 90 days"), money(s.ageing.over_90)],
		]);
		html += `<p><strong>${__("Payment behaviour")}</strong> · ${reviewDate(data.from_date)} — ${reviewDate(data.as_of)}</p>`;
		html += reviewTable(["Measure", "Result"], [
			[__("Credit invoices / instalments with completed due dates"), reviewNumber(stats.due_terms)],
			[__("Fully paid by due date"), `${reviewNumber(stats.paid_on_time)} / ${reviewNumber(stats.due_terms)} (${stats.on_time_percent == null ? __("Insufficient history") : `${reviewNumber(stats.on_time_percent)}%`})`],
			[__("Fully paid late"), reviewNumber(stats.paid_late)],
			[__("Overdue and not fully paid"), reviewNumber(stats.overdue_unpaid)],
			[__("Average delay among late fully paid instalments"), stats.average_days_late == null ? "—" : `${reviewNumber(stats.average_days_late)} ${__("days")}`],
			[__("Longest delay among late fully paid instalments"), stats.longest_paid_delay == null ? "—" : `${reviewNumber(stats.longest_paid_delay)} ${__("days")}`],
			[__("Due instalments excluded: paid at sale or requiring review"), reviewNumber(stats.excluded_terms)],
		]);
		html += reviewTable(["Recent Period", "Due Instalments", "Paid By Due Date", "Paid Late", "Overdue Unpaid"], data.trends.map(row => [
			`${reviewNumber(row.months)} ${__("months")}`, reviewNumber(row.due_terms),
			row.on_time_percent == null ? "—" : `${reviewNumber(row.on_time_percent)}%`, reviewNumber(row.paid_late), reviewNumber(row.overdue_unpaid),
		]));
		html += `<p><strong>${__("Invoice history")}</strong> · ${reviewNumber(data.invoice_count)} ${__("invoices")}</p>`;
		if (data.invoice_count > data.invoices.length) html += `<p class="text-muted small">${__("Showing the latest 200 invoices. Summary calculations include all matching records.")}</p>`;
		html += reviewTable(["Invoice", "Invoice Date", "Invoice Amount", "Allocated Receipts / Refunds", "Other Settlement", "Balance", "Status", "Details"], data.invoices.map(row => [
			reviewLink("Sales Invoice", row.invoice), reviewDate(row.posting_date), reviewMoney(row.amount, row.currency),
			reviewMoney(row.allocated_receipts, row.currency), reviewMoney(row.other_settlement, row.currency), reviewMoney(row.balance, row.currency),
			reviewEscape(__(row.status)), `<details><summary>${__("Due dates and allocations")}</summary>${renderCreditInvoiceDetails(row)}</details>`,
		]));
		html += `<p><strong>${__("Payment history")}</strong> · ${reviewNumber(data.payment_count)} ${__("payments")}</p>`;
		if (data.payment_count > data.payments.length) html += `<p class="text-muted small">${__("Showing the latest 200 payments. Older unallocated receipts remain included in current balances.")}</p>`;
		html += reviewTable(["Payment", "Date", "Type / Status", "Amount", "Unallocated", "Mode", "Reference Date", "Clearance Date"], data.payments.map(row => [
			reviewLink("Payment Entry", row.name), reviewDate(row.posting_date),
			reviewEscape(row.docstatus === 2 ? __("Cancelled — excluded") : __(row.payment_type)),
			reviewMoney(row.payment_type === "Receive" ? row.received_amount : row.paid_amount,
				row.payment_type === "Receive" ? row.paid_to_account_currency : row.paid_from_account_currency),
			reviewMoney(row.unallocated_amount, row.payment_type === "Receive" ? row.paid_from_account_currency : row.paid_to_account_currency),
			reviewEscape(row.mode_of_payment || "—"), reviewDate(row.reference_date), reviewDate(row.clearance_date),
		]));
		return html;
	}

	function renderCreditInvoiceDetails(row) {
		return `${row.issues.map(issue => `<p class="text-warning small">${reviewEscape(__(issue))}</p>`).join("")}${reviewTable(
			["Instalment", "Due Date", "Amount", "Balance", "Fully Settled On", "Timing"],
			row.terms.map(term => [reviewEscape(term.term || "—"), reviewDate(term.due_date), reviewMoney(term.amount, row.currency),
				reviewMoney(term.balance, row.currency), reviewDate(term.full_payment_date), reviewEscape(__(term.timing))]))}${reviewTable(
			["Document", "Date", "Settlement Type", "Amount", "Payment Term"],
			row.events.map(event => [reviewLink(event.doctype, event.name), reviewDate(event.date), reviewEscape(__(event.kind)),
				reviewMoney(event.amount, row.currency), reviewEscape(event.term || "—")]))}`;
	}

	function updateSupplierStockButton(frm) {
		const label = __("View Supplier Stock");
		frm.remove_custom_button(label);
		if (frm.doc.payment_type !== "Pay" || frm.doc.party_type !== "Supplier" ||
			!frm.doc.party || !frm.doc.company) return;

		frm.add_custom_button(label, () => {
			const toDate = frappe.datetime.get_today();
			frappe.set_route("query-report", "Slow Moving Items", {
				company: frm.doc.company,
				supplier: frm.doc.party,
				from_date: frappe.datetime.add_days(toDate, -90),
				to_date: toDate,
				warehouse: "",
				item_group: "",
				brand: "",
				only_with_stock: 1,
				only_no_sales: 1,
				max_net_qty: 0,
				limit: 100,
			});
		});
	}

	function applyVanInvoiceContext(frm) {
		const invoiceName = getReferencedSalesInvoice(frm);
		if (!invoiceName) return;

		frappe.db.get_value(
			"Sales Invoice",
			invoiceName,
			["custom_is_van_sale", "custom_van_session"]
		).then((response) => {
			const invoice = response.message || {};
			if (cint(invoice.custom_is_van_sale) !== 1) return;

			const values = { custom_is_van_payment: 1 };
			if (invoice.custom_van_session) {
				values.custom_van_session = invoice.custom_van_session;
			}

			frm.set_value(values).then(() => fetchVanSessionDetails(frm));
		});
	}

	function getReferencedSalesInvoice(frm) {
		const routeOptions = frappe.route_options || {};
		if (routeOptions.reference_doctype === "Sales Invoice" && routeOptions.reference_name) {
			return routeOptions.reference_name;
		}

		const reference = (frm.doc.references || []).find((row) => {
			return row.reference_doctype === "Sales Invoice" && row.reference_name;
		});
		return reference?.reference_name;
	}

	function fetchVanSessionDetails(frm) {
		if (cint(frm.doc.custom_is_van_payment) !== 1 || !frm.doc.custom_van_session) return;

		frappe.db.get_value(
			"Van Session",
			frm.doc.custom_van_session,
			["van", "driver", "driver_name"]
		).then((response) => {
			const session = response.message || {};
			const values = {};

			if (session.van) values.custom_van = session.van;
			if (session.driver) values.custom_driver = session.driver;
			if (session.driver_name) values.custom_driver_name = session.driver_name;

			if (Object.keys(values).length) {
				frm.set_value(values);
			}
		});
	}
})();

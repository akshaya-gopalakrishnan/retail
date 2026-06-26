frappe.ui.form.on("POS Branch Day Closing", {
	setup(frm) {
		hide_raw_total_fields(frm);
	},
	refresh(frm) {
		hide_raw_total_fields(frm);
		add_day_closing_actions(frm);
		render_status_totals(frm);
	},
	branch(frm) {
		render_status_totals(frm);
	},
	business_date(frm) {
		render_status_totals(frm);
	},
	total_cashier_shifts(frm) {
		render_status_totals(frm);
	},
	open_shift_count(frm) {
		render_status_totals(frm);
	},
	active_counter_session_count(frm) {
		render_status_totals(frm);
	},
	total_sales(frm) {
		render_status_totals(frm);
	},
	total_expected_cash(frm) {
		render_status_totals(frm);
	},
	total_closing_cash(frm) {
		render_status_totals(frm);
	},
	total_variance(frm) {
		render_status_totals(frm);
	},
});

function hide_raw_total_fields(frm) {
	const fields = [
		"manager_user",
		"closed_at",
		"total_cashier_shifts",
		"open_shift_count",
		"closed_shift_count",
		"active_counter_session_count",
		"totals_section",
		"total_invoice_count",
		"total_sales",
		"total_expected_cash",
		"total_closing_cash",
		"total_variance",
	];

	fields.forEach((fieldname) => frm.toggle_display(fieldname, false));
}

function add_day_closing_actions(frm) {
	if (frm.doc.docstatus !== 0 || !frm.doc.branch || !frm.doc.business_date) return;

	frm.add_custom_button(__("Refresh Closing"), () => {
		frappe.call({
			method: "retail.api.pos_sync.make_branch_day_closing",
			args: {
				data: {
					branch: frm.doc.branch,
					business_date: frm.doc.business_date,
				},
			},
			freeze: true,
			freeze_message: __("Refreshing closing totals"),
			callback: (response) => {
				if (response.message?.name) {
					frappe.set_route("Form", "POS Branch Day Closing", response.message.name);
				}
			},
		});
	});
}

function render_status_totals(frm) {
	if (!frm.fields_dict.status_totals_html) return;

	const open_shifts = cint(frm.doc.open_shift_count);
	const active_sessions = cint(frm.doc.active_counter_session_count);
	const is_ready = open_shifts === 0 && active_sessions === 0 && cint(frm.doc.total_cashier_shifts) > 0;
	const status_label = frm.doc.docstatus === 1 ? "Day Closed" : is_ready ? "Ready To Close" : "Pending Closures";
	const status_class = frm.doc.docstatus === 1 ? "closed" : is_ready ? "ready" : "pending";
	const money = (value) => format_currency(flt(value), frappe.defaults.get_default("currency"));
	const variance = flt(frm.doc.total_variance);
	const variance_class = variance === 0 ? "ok" : variance > 0 ? "over" : "short";
	const blockers = [];

	if (!cint(frm.doc.total_cashier_shifts)) blockers.push(__("No cashier shifts found for this date."));
	if (open_shifts) blockers.push(__("{0} cashier shift(s) still open.", [open_shifts]));
	if (active_sessions) blockers.push(__("{0} counter session(s) still active.", [active_sessions]));
	if (frm.doc.docstatus === 1) blockers.push(__("This day closing has already been submitted."));

	const decision_text =
		frm.doc.docstatus === 1
			? __("Final day closing completed.")
			: is_ready
				? __("All shifts are closed. Review variance and submit.")
				: __("Close pending cashier shifts before submitting.");

	const html = `
		<style>
			.pos-day-close-summary {
				margin: 4px 0 12px;
			}
			.pos-day-close-hero {
				display: flex;
				justify-content: space-between;
				gap: 16px;
				align-items: flex-start;
				padding: 14px 16px;
				border: 1px solid var(--border-color);
				border-radius: 8px;
				background: var(--fg-color);
			}
			.pos-day-close-title {
				font-size: 15px;
				font-weight: 700;
				margin-bottom: 5px;
			}
			.pos-day-close-context {
				color: var(--text-muted);
				font-size: 12px;
			}
			.pos-day-close-pill {
				display: inline-flex;
				align-items: center;
				min-height: 26px;
				padding: 0 10px;
				border-radius: 999px;
				font-weight: 700;
				font-size: 12px;
				white-space: nowrap;
			}
			.pos-day-close-pill.ready {
				background: #e7f7ee;
				color: #137a3f;
			}
			.pos-day-close-pill.pending {
				background: #fff3da;
				color: #9a5b00;
			}
			.pos-day-close-pill.closed {
				background: #e8f0ff;
				color: #1f5fbf;
			}
			.pos-day-close-grid {
				display: grid;
				grid-template-columns: repeat(4, minmax(0, 1fr));
				gap: 10px;
				margin-top: 12px;
			}
			.pos-day-close-metric {
				border: 1px solid var(--border-color);
				border-radius: 8px;
				padding: 12px;
				background: var(--fg-color);
				min-height: 78px;
			}
			.pos-day-close-metric .label {
				color: var(--text-muted);
				font-size: 11px;
				font-weight: 700;
				text-transform: uppercase;
			}
			.pos-day-close-metric .value {
				font-size: 20px;
				font-weight: 700;
				margin-top: 6px;
				line-height: 1.2;
			}
			.pos-day-close-metric .hint {
				color: var(--text-muted);
				font-size: 12px;
				margin-top: 4px;
			}
			.pos-day-close-metric.warning .value,
			.pos-day-close-variance.short {
				color: #b42318;
			}
			.pos-day-close-variance.over {
				color: #9a5b00;
			}
			.pos-day-close-variance.ok {
				color: #137a3f;
			}
			.pos-day-close-blockers {
				margin-top: 10px;
				padding: 10px 12px;
				border-radius: 8px;
				background: ${is_ready || frm.doc.docstatus === 1 ? "#eef8f1" : "#fff7e8"};
				color: ${is_ready || frm.doc.docstatus === 1 ? "#17633a" : "#805200"};
				font-size: 12px;
				font-weight: 600;
			}
			@media (max-width: 900px) {
				.pos-day-close-hero {
					flex-direction: column;
				}
				.pos-day-close-grid {
					grid-template-columns: repeat(2, minmax(0, 1fr));
				}
			}
		</style>
		<div class="pos-day-close-summary">
			<div class="pos-day-close-hero">
				<div>
					<div class="pos-day-close-title">${frappe.utils.escape_html(decision_text)}</div>
					<div class="pos-day-close-context">
						${frappe.utils.escape_html(frm.doc.branch || "-")} · ${frappe.utils.escape_html(frm.doc.business_date || "-")}
						${frm.doc.manager_user ? ` · ${frappe.utils.escape_html(frm.doc.manager_user)}` : ""}
					</div>
				</div>
				<span class="pos-day-close-pill ${status_class}">${status_label}</span>
			</div>

			<div class="pos-day-close-grid">
				<div class="pos-day-close-metric">
					<div class="label">${__("Total Sales")}</div>
					<div class="value">${money(frm.doc.total_sales)}</div>
					<div class="hint">${cint(frm.doc.total_invoice_count)} ${__("invoice(s)")}</div>
				</div>
				<div class="pos-day-close-metric">
					<div class="label">${__("Cash To Receive")}</div>
					<div class="value">${money(frm.doc.total_expected_cash)}</div>
					<div class="hint">${__("Expected cash")}</div>
				</div>
				<div class="pos-day-close-metric">
					<div class="label">${__("Cash Counted")}</div>
					<div class="value">${money(frm.doc.total_closing_cash)}</div>
					<div class="hint">${__("Cashier closing cash")}</div>
				</div>
				<div class="pos-day-close-metric ${variance ? "warning" : ""}">
					<div class="label">${__("Variance")}</div>
					<div class="value pos-day-close-variance ${variance_class}">${money(frm.doc.total_variance)}</div>
					<div class="hint">${variance === 0 ? __("Balanced") : __("Review before closing")}</div>
				</div>
				<div class="pos-day-close-metric ${open_shifts ? "warning" : ""}">
					<div class="label">${__("Open Shifts")}</div>
					<div class="value">${open_shifts}</div>
					<div class="hint">${cint(frm.doc.total_cashier_shifts)} ${__("total shift(s)")}</div>
				</div>
				<div class="pos-day-close-metric ${active_sessions ? "warning" : ""}">
					<div class="label">${__("Active Counters")}</div>
					<div class="value">${active_sessions}</div>
					<div class="hint">${__("Must be zero")}</div>
				</div>
				<div class="pos-day-close-metric">
					<div class="label">${__("Closed Shifts")}</div>
					<div class="value">${cint(frm.doc.closed_shift_count)}</div>
					<div class="hint">${__("Cashier shifts closed")}</div>
				</div>
				<div class="pos-day-close-metric">
					<div class="label">${__("Document")}</div>
					<div class="value">${frm.doc.docstatus === 1 ? __("Submitted") : __("Draft")}</div>
					<div class="hint">${frm.doc.closed_at ? frappe.utils.escape_html(frm.doc.closed_at) : __("Not submitted")}</div>
				</div>
			</div>

			<div class="pos-day-close-blockers">
				${blockers.length ? blockers.map((item) => `<div>${frappe.utils.escape_html(item)}</div>`).join("") : __("Ready for manager review and submit.")}
			</div>
		</div>
	`;

	frm.fields_dict.status_totals_html.$wrapper.html(html);
}

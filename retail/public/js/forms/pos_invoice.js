frappe.ui.form.on("POS Invoice", {
	async refresh(frm) {
		if (frm.is_new()) return;
		const name = frm.doc.name;
		const { message: posting } = await frappe.call({
			method: "retail.pos_ledger.get_ledger_context",
			args: { pos_invoice: name },
		});
		if (frm.doc.name !== name || !posting) return;

		if (!posting.posted) {
			frm.dashboard.set_headline_alert(
				posting.cancelled
					? __("This POS receipt is cancelled and has no linked accounting invoice.")
					: __("Not posted yet. Ledger views will be available after accounting is posted.")
			);
			return;
		}

		if (posting.combined) {
			frm.dashboard.set_headline_alert(
				__("This receipt shares a consolidated Sales Invoice with other POS receipts. Ledger views show the combined posting.")
			);
		}

		const open_ledger = (report) => {
			frappe.route_options = {
				company: posting.company,
				voucher_no: posting.voucher_no,
				from_date: posting.posting_date,
				to_date: posting.posting_date,
				show_cancelled_entries: posting.cancelled,
				ignore_prepared_report: true,
			};
			if (report === "General Ledger") {
				frappe.route_options.categorize_by = "Categorize by Voucher (Consolidated)";
			}
			frappe.set_route("query-report", report);
		};

		const reports = frappe.boot.user.all_reports || {};
		if (reports["General Ledger"]) {
			frm.add_custom_button(__("Accounting Ledger"), () => open_ledger("General Ledger"), __("View"));
		}
		if (posting.update_stock && reports["Stock Ledger"]) {
			frm.add_custom_button(__("Stock Ledger"), () => open_ledger("Stock Ledger"), __("View"));
		}
		frm.add_custom_button(__("Linked Sales Invoice"), () => {
			frappe.set_route("Form", "Sales Invoice", posting.voucher_no);
		}, __("View"));
	},
});

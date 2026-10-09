(() => {
	const labels = {
		"Accounts Payable": "Total Payable: {0}",
		"Accounts Receivable": "Total Receivable: {0}",
	};
	const selector = ".retail-outstanding-footer";
	const clear = () => $(selector).remove();

	frappe.router.on("change", clear);
	// Desk loads report.bundle.js before app_include_js customizations.
	const prototype = frappe.views.QueryReport.prototype;
	if (prototype.__retail_outstanding_footer) return;
	prototype.__retail_outstanding_footer = true;
	const refresh = prototype.refresh;

	prototype.refresh = function () {
		clear();
		const report_name = this.report_name;
		const result = refresh.apply(this, arguments);
		if (!labels[report_name]) return result;

		return result.then((value) => {
			const route = frappe.get_route();
			if (route[0] !== "query-report" || route[1] !== report_name) return value;
			if (this.report_name !== report_name) return value;

			let rows = this.data || [];
			// Frappe appends a grand total; grouped reports also emit bold subtotals.
			if (this.raw_data?.add_total_row && rows.length) rows = rows.slice(0, -1);
			rows = rows.filter((row) => !row.is_total_row && !(row.bold && !row.voucher_no));
			const total = rows.reduce(
				(sum, row) => sum + flt(row.outstanding_amount ?? row.outstanding),
				0
			);
			const currency = rows.find((row) => row.currency)?.currency ||
				erpnext.get_currency(this.get_filter_value("company"));

			clear();
			$("<div>", { class: "retail-outstanding-footer", "aria-hidden": "true" })
				.css("height", "68px")
				.appendTo(this.page.main);
			$("<div>", { class: "retail-outstanding-footer", role: "status" })
				.text(__(labels[report_name], [format_currency(total, currency)]))
				.css({
					position: "fixed",
					bottom: 0,
					left: 0,
					right: 0,
					zIndex: 100,
					padding: "16px 24px",
					textAlign: "right",
					fontSize: "20px",
					lineHeight: "28px",
					fontWeight: 800,
					background: "var(--card-bg)",
					borderTop: "1px solid var(--border-color)",
				})
				// Keep fixed positioning relative to the viewport, outside themed panels.
				.appendTo(document.body);
			return value;
		});
	};
})();

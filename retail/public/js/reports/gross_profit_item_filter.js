(function () {
	const REPORT_NAME = "Gross Profit";

	function add_item_filter(settings) {
		if (!settings || !Array.isArray(settings.filters)) return;
		if (settings.filters.some((filter) => filter.fieldname === "item_code")) return;

		const salesInvoiceIndex = settings.filters.findIndex(
			(filter) => filter.fieldname === "sales_invoice"
		);
		const insertAt = salesInvoiceIndex >= 0 ? salesInvoiceIndex + 1 : settings.filters.length;

		settings.filters.splice(insertAt, 0, {
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
			get_query: function () {
				return {
					filters: {
						is_sales_item: 1,
						disabled: 0,
					},
				};
			},
		});
	}

	function patch_query_report() {
		const QueryReport = frappe?.views?.QueryReport;
		if (!QueryReport?.prototype?.get_report_settings) return false;
		if (QueryReport.prototype.__retail_gross_profit_item_filter) return true;

		const original = QueryReport.prototype.get_report_settings;

		QueryReport.prototype.get_report_settings = function () {
			return Promise.resolve(original.apply(this, arguments)).then((result) => {
				if (this.report_name === REPORT_NAME) {
					add_item_filter(this.report_settings);
					add_item_filter(frappe.query_reports?.[REPORT_NAME]);
				}

				return result;
			});
		};

		QueryReport.prototype.__retail_gross_profit_item_filter = true;
		return true;
	}

	if (!patch_query_report()) {
		const timer = setInterval(() => {
			if (patch_query_report()) clearInterval(timer);
		}, 100);

		setTimeout(() => clearInterval(timer), 10000);
	}
})();

frappe.query_reports["Expired Items"] = {
	filters: [
		{
			fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
			reqd: 1, default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "as_of_date", label: __("As of Date"), fieldtype: "Date",
			reqd: 1, default: frappe.datetime.get_today(),
		},
		{
			fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse",
			get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } }),
		},
		{ fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item" },
		{
			fieldname: "batch_no", label: __("Batch"), fieldtype: "Link", options: "Batch",
			get_query: () => ({ filters: frappe.query_report.get_filter_value("item_code")
				? { item: frappe.query_report.get_filter_value("item_code") } : {} }),
		},
		{ fieldname: "supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier" },
		{ fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
		{ fieldname: "brand", label: __("Brand"), fieldtype: "Link", options: "Brand" },
		{ fieldname: "include_depleted", label: __("Include Depleted Batches"), fieldtype: "Check", default: 0 },
	],
	onload(report) {
		report.page.add_inner_button(__("Clear Filters"), async () => {
			// Keep the required company/date context and clear all optional selections.
			report._no_refresh = true;
			try {
				await frappe.after_ajax();
				await Promise.all(report.filters.filter(filter => !filter.df.reqd).map(filter =>
					filter.set_value(filter.df.fieldtype === "Check" ? 0 : "")
				));
			} finally {
				report._no_refresh = false;
			}
			report.previous_filters = null;
			report.__retail_clear_expired_column_filters = true;
			report.refresh(true);
		});
		report.page.add_inner_button(__("Batch Stock Ledger"), () => {
			const filters = report.get_values();
			if (!filters.batch_no) {
				frappe.msgprint(__("Select a Batch filter to view its stock movements."));
				return;
			}
			frappe.route_options = {
				company: filters.company, batch_no: filters.batch_no,
				from_date: "1900-01-01", to_date: filters.as_of_date,
				...(filters.item_code ? { item_code: [filters.item_code] } : {}),
				...(filters.warehouse ? { warehouse: [filters.warehouse] } : {}),
			};
			frappe.set_route("query-report", "Stock Ledger");
		});
	},
	after_datatable_render(datatable) {
		const report = frappe.query_report;
		if (!report.__retail_clear_expired_column_filters) return;
		delete report.__retail_clear_expired_column_filters;
		datatable.wrapper.querySelectorAll(".dt-filter").forEach(input => { input.value = ""; });
		datatable.columnmanager.applyFilter({});
	},
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (data && ["remaining_qty", "expired_stock_value"].includes(column.fieldname) && value > 0) {
			return `<span class="text-danger">${formatted}</span>`;
		}
		return formatted;
	},
};

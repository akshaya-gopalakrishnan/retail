frappe.query_reports["POS Invoice Profit"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: [
		...get_pos_report_filters().map(filter => {
			if (filter.fieldname === "company") return { ...filter, reqd: 1 };
			if (["from_date", "to_date"].includes(filter.fieldname)) {
				return {
					...filter,
					label: filter.fieldname === "from_date" ? __("From Date") : __("End Date"),
					default: frappe.datetime.get_today(),
					reqd: 1,
				};
			}
			return filter;
		}),
		{ fieldname: "pos_invoice", label: __("POS Invoice"), fieldtype: "Link", options: "POS Invoice" },
	],
};

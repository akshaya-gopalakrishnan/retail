frappe.query_reports["POS Item-wise Sales"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters({ include_item_filters: true }).concat([
		{ fieldname: "serial_no", label: __("Serial No"), fieldtype: "Link", options: "Serial No" },
		{ fieldname: "batch_no", label: __("Batch"), fieldtype: "Link", options: "Batch" },
		{ fieldname: "serial_and_batch_bundle", label: __("Serial and Batch Bundle"), fieldtype: "Link", options: "Serial and Batch Bundle" },
	]),
};

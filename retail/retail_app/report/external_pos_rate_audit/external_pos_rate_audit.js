frappe.query_reports["External POS Rate Audit"] = {
	filters: get_pos_report_filters({ include_cashier: true, include_item_filters: true }).concat([
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nOpen\nAccepted\nIgnored\nRecalculated",
			default: "Open",
		},
	]),

	onload(report) {
		report.page.add_inner_button(__("Accept All Open"), () => {
			frappe.confirm(__("Accept all open audit rows matching the current filters?"), () => {
				frappe.call({
					method: "retail.pos_rate_audit.accept_all",
					args: { filters: report.get_values() },
					callback(response) {
						frappe.show_alert({
							message: __("Accepted {0} audit rows", [response.message.updated || 0]),
							indicator: "green",
						});
						report.refresh();
					},
				});
			});
		});
	},
};

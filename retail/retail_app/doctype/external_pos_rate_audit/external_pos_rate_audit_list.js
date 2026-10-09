frappe.listview_settings["External POS Rate Audit"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Accept All Open"), () => {
			frappe.confirm(__("Accept all open External POS Rate Audit rows in the current filters?"), () => {
				frappe.call({
					method: "retail.pos_rate_audit.accept_all",
					args: { filters: listview.filter_area.get() },
					callback(response) {
						frappe.show_alert({
							message: __("Accepted {0} audit rows", [response.message.updated || 0]),
							indicator: "green",
						});
						listview.refresh();
					},
				});
			});
		});
	},
};

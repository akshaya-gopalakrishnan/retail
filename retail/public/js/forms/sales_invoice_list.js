(function () {
	const settings = frappe.listview_settings["Sales Invoice"] || {};
	const existing_onload = settings.onload;

	settings.onload = function (listview) {
		if (existing_onload) {
			existing_onload(listview);
		}

		const set_channel_filter = (channel) => {
			frappe.model.with_doctype("Sales Invoice", () => {
				listview.filter_area.remove("is_pos").then(() => listview.filter_area.remove("sales_channel")).then(() => {
					if (channel) {
						return listview.filter_area.add("Sales Invoice", "sales_channel", "=", channel);
					}

					listview.refresh();
				});
			});
		};

		listview.page.add_inner_button(__("Trading Invoices"), () => set_channel_filter("Trading"));

		if (frappe.user.has_role("System Manager") || frappe.user.has_role("Accounts Manager")) {
			listview.page.add_inner_button(__("POS Invoices"), () => set_channel_filter("POS"));
			listview.page.add_inner_button(__("All Invoices"), () => set_channel_filter(null));
		}
	};

	frappe.listview_settings["Sales Invoice"] = settings;
})();

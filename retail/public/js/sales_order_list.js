(() => {
	const settings = frappe.listview_settings["Sales Order"];
	const original_onload = settings.onload;
	const original_refresh = settings.refresh;
	settings.onload = function (listview) {
		original_onload?.call(this, listview);
		const fields = listview.page.fields_dict;
		for (const fieldname of ["customer_name", "company"]) {
			fields[fieldname]?.$wrapper.remove();
			delete fields[fieldname];
		}
		if (frappe.session.user === "Administrator" || frappe.user.has_role("Super Admin")) {
			listview.retail_api_logs_button = listview.page.add_inner_button(__("API Logs"), () => {
				frappe.set_route("List", "Sales Order API Log");
			});
		}
	};
	settings.refresh = function (listview) {
		original_refresh?.call(this, listview);
		// Frappe builds the view selector after onload; position once it exists.
		if (listview.retail_api_logs_button && listview.views_menu) {
			listview.retail_api_logs_button.insertAfter(listview.views_menu.closest(".custom-btn-group"));
		}
	};
})();

(() => {
	const settings = frappe.listview_settings["Sales Order"];
	const original_onload = settings.onload;
	settings.onload = function (listview) {
		original_onload?.call(this, listview);
		const fields = listview.page.fields_dict;
		for (const fieldname of ["customer_name", "company"]) {
			fields[fieldname]?.$wrapper.remove();
			delete fields[fieldname];
		}


	};
})();

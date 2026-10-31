frappe.listview_settings["POS Sync Log"] = {
	onload(listview) {
		for (const [label, doctype] of [
			["Settlement Exception", "POS Settlement Exception"],
			["Rate Audit", "External POS Rate Audit"],
		]) {
			listview.page.add_inner_button(__(label), () => {
				frappe.route_options = { name: ["is", "set"] };
				frappe.set_route("List", doctype);
			});
		}
	},
};

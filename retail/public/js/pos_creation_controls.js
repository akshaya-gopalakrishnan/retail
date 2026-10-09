(function () {
	const blocked_pos_doctypes = new Set([
		"POS Invoice",
		"POS Opening Entry",
		"POS Closing Entry",
		"POS Cashier Shift",
		"POS Counter Session",
		"POS Sync Log",
	]);

	if (frappe.views.ListView.prototype.retail_pos_create_guard) return;

	const set_primary_action = frappe.views.ListView.prototype.set_primary_action;

	frappe.views.ListView.prototype.set_primary_action = function () {
		if (blocked_pos_doctypes.has(this.doctype)) {
			this.page.clear_primary_action();
			return;
		}

		return set_primary_action.apply(this, arguments);
	};

	frappe.views.ListView.prototype.retail_pos_create_guard = true;
})();

(function () {
	const settings = frappe.listview_settings["POS Invoice"] ||= {};
	const original_onload = settings.onload;
	settings.onload = function (listview) {
		if (original_onload) original_onload.call(this, listview);
		if (!frappe.boot.user.all_reports?.["POS Invoice Profit"]) return;
		listview.page.add_inner_button(__("Daily Sales & Profit"), () => {
			frappe.set_route("query-report", "POS Invoice Profit", {
				from_date: frappe.datetime.get_today(),
				to_date: frappe.datetime.get_today(),
			});
		});
	};
})();

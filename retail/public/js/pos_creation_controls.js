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
		for (const fieldname of ["company", "title"]) {
			listview.page.fields_dict[fieldname]?.$wrapper.remove();
			delete listview.page.fields_dict[fieldname];
		}
		const wrapper = listview.filter_area.standard_filters_wrapper;
		wrapper.addClass("retail-pos-invoice-filters");
		for (const [fieldname, label] of [
			["custom_pos_business_date", "Business Date"], ["posting_date", "Posting Date"],
		]) {
			if (!listview.page.fields_dict[fieldname]) {
				listview.page.add_field({
					fieldname, label: __(label), fieldtype: "Date", condition: "=",
					onchange: () => listview.filter_area.debounced_refresh_list_view(),
				}, wrapper);
			}
			listview.page.fields_dict[fieldname].$wrapper.addClass("retail-pos-date-filter");
		}
		for (const [index, fieldname] of ["name", "custom_pos_business_date", "posting_date",
			"customer", "custom_pos_transaction_type", "status", "pos_cashier_employee",
			"pos_cashier_shift", "pos_counter_session"].entries()) {
			listview.page.fields_dict[fieldname]?.$wrapper.css("order", index);
		}
		if (!document.getElementById("retail-pos-invoice-filter-style")) {
			$("<style id='retail-pos-invoice-filter-style'>").text(`
				.retail-pos-invoice-filters {
					display: flex !important; flex-wrap: wrap;
					gap: 10px 12px; padding: 12px 8px; width: 100%;
				}
				.retail-pos-invoice-filters > .frappe-control {
					flex: 0 0 auto; width: var(--retail-filter-width, 140px) !important;
					min-width: 0 !important; max-width: 100%;
					margin: 0 !important; padding: 0 !important; order: 20;
				}
				.retail-pos-invoice-filters .form-group { margin-bottom: 0; }
			`).appendTo(document.head);
		}
		const measure = document.createElement("canvas").getContext("2d");
		const fit_filters = () => {
			wrapper.children(".frappe-control").each(function () {
				const input = this.querySelector("input:not([type=hidden]), select");
				if (!input) return;
				measure.font = getComputedStyle(input).font;
				const placeholder = input.getAttribute("placeholder") || this.getAttribute("title") || "";
				const value = input.tagName === "SELECT"
					? input.selectedOptions[0]?.textContent || "" : input.value;
				const text_width = Math.max(measure.measureText(placeholder).width,
					measure.measureText(value).width,
					this.classList.contains("retail-pos-date-filter") ? measure.measureText("00-00-0000").width : 0);
				// Leave room for input padding and the link/date/select icon.
				this.style.setProperty("--retail-filter-width", `${Math.ceil(text_width) + 48}px`);
			});
		};
		wrapper.on("input.retail_filter_width change.retail_filter_width", "input, select", fit_filters);
		// Item, serial and batch controls are added by the next list onload handler.
		requestAnimationFrame(fit_filters);
		listview.page.show_form();
		if (!frappe.boot.user.all_reports?.["POS Invoice Profit"]) return;
		listview.page.add_inner_button(__("Daily Sales & Profit"), () => {
			frappe.set_route("query-report", "POS Invoice Profit", {
				from_date: frappe.datetime.get_today(),
				to_date: frappe.datetime.get_today(),
			});
		});
	};
})();

// Keep the invoice number available for lookup alongside the customer title.
(() => {
	const settings = frappe.listview_settings["Sales Invoice"];
	const original_onload = settings.onload;
	settings.onload = function (listview) {
		original_onload?.call(this, listview);
		setupInvoiceSourceView(listview);
		const wrapper = listview.filter_area.standard_filters_wrapper;
		const fields = listview.page.fields_dict;
		fields.company?.$wrapper.remove();
		delete fields.company;

		const label = __("Sales Invoice Code");
		for (const [fieldname, field_label] of [["name", label], ["title", __("Title")]]) {
			const previous_value = fields[fieldname]?.get_value() || "";
			fields[fieldname]?.$wrapper.remove();
			delete fields[fieldname];
			const control = listview.page.add_field({
				fieldname,
				fieldtype: "Autocomplete",
				label: field_label,
				condition: "like",
				ignore_validation: true,
				onchange: () => listview.filter_area.debounced_refresh_list_view(),
			}, wrapper);
			control.set_input(previous_value);
			let request = 0;
			const suggest = frappe.utils.debounce(async () => {
				const sequence = ++request;
				const term = control.$input.val() || "";
				const rows = await frappe.db.get_list("Sales Invoice", {
					fields: [fieldname],
					filters: [[fieldname, "like", `%${term}%`],
						["is_consolidated", "=", listview.retail_pos_invoices ? 1 : 0]],
					distinct: true,
					order_by: `${fieldname} asc`,
					limit: 30,
				});
				if (sequence !== request || term !== control.$input.val()) return;
				control.set_data(rows.filter(row => row[fieldname]).map(row => ({
					value: row[fieldname],
					label: frappe.utils.escape_html(row[fieldname]),
				})));
				if (control.$input.is(":focus")) control.awesomplete.evaluate();
			}, 200);
			control.$input.on("input focus", suggest);
		}
		fields.name.$wrapper.prependTo(wrapper);
		fields.title.$wrapper.insertAfter(fields.name.$wrapper);
		listview.page.show_form();


	};
	function setupInvoiceSourceView(listview) {
		const canViewPOS = () => (frappe.user_roles || []).includes("POS Manager");
		listview.retail_pos_invoices = false;
		const originalFilters = listview.get_filters_for_args.bind(listview);
		listview.get_filters_for_args = function () {
			const filters = originalFilters().filter(f =>
				!(f[0] === "Sales Invoice" && f[1] === "is_consolidated"));
			filters.push(["Sales Invoice", "is_consolidated", "=",
				canViewPOS() && this.retail_pos_invoices ? 1 : 0]);
			return filters;
		};
		listview.retail_reset_invoice_source = () => {
			const changed = listview.retail_pos_invoices;
			listview.retail_pos_invoices = false;
			listview.page.set_title(__("Sales Invoice"));
			return changed;
		};
		if (!canViewPOS()) return;
		listview.page.add_inner_button(__("POS Invoices"), () => {
			if (!canViewPOS()) return;
			listview.retail_pos_invoices = !listview.retail_pos_invoices;
			listview.page.set_title(listview.retail_pos_invoices
				? __("POS-generated Sales Invoices") : __("Sales Invoice"));
			listview.start = 0;
			listview.refresh();
		});
	}
})();

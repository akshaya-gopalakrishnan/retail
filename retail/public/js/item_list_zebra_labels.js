frappe.listview_settings["Item"] = frappe.listview_settings["Item"] || {};
frappe.listview_settings["Item"].add_fields = [
	...new Set([...(frappe.listview_settings["Item"].add_fields || []), "item_code"]),
];

function arrangeRetailItemFilters(listview) {
	const wrapper = listview.filter_area.standard_filters_wrapper;
	const row = (className) => {
		let element = wrapper.children(`.${className}`);
		if (!element.length) element = $("<div>").addClass(className).appendTo(wrapper);
		return element.css({ display: "flex", flexWrap: "wrap", width: "100%" });
	};
	const boxed = row("retail-item-filter-boxes");
	const checks = row("retail-item-filter-checks");
	const order = ["custom_document_code", "name", "item_code", "item_name", "custom_barcode",
		"item_group", "variant_of", "custom_scale_item", "has_variants", "has_batch_no", "has_serial_no"];
	const rank = key => order.includes(key) ? order.indexOf(key) : order.length;
	Object.entries(listview.page.fields_dict)
		.sort(([a], [b]) => rank(a) - rank(b))
		.forEach(([, control]) => control.$wrapper.appendTo(control.df.fieldtype === "Check" ? checks : boxed));
}

const originalRetailItemFilterRefresh = frappe.listview_settings["Item"].refresh;
frappe.listview_settings["Item"].refresh = function (listview) {
	originalRetailItemFilterRefresh?.call(this, listview);
	arrangeRetailItemFilters(listview);
};

frappe.listview_settings["Item"].onload = function (listview) {
	const wrapper = listview.filter_area.standard_filters_wrapper;
	const previous_name = listview.page.fields_dict.item_name;
	const previous_name_value = previous_name?.get_value() || "";
	previous_name?.$wrapper.remove();
	delete listview.page.fields_dict.item_name;
	const item_name = listview.page.add_field({
		fieldname: "item_name",
		fieldtype: "Autocomplete",
		label: __("Item Name"),
		condition: "like",
		ignore_validation: true,
		onchange: () => listview.filter_area.debounced_refresh_list_view(),
	}, wrapper);
	item_name.set_input(previous_name_value);
	// The server already applies LIKE, including restored wildcard filters.
	item_name.awesomplete.filter = () => true;
	// Render master names as text while retaining their exact filter values.
	item_name.awesomplete.item = suggestion => $("<li>")
		.data("item.autocomplete", { value: suggestion.value, label: suggestion.label })
		.attr("aria-selected", "false").append($("<p>").text(suggestion.label)).get(0);
	let name_request = 0;
	const suggest_names = frappe.utils.debounce(async () => {
		const sequence = ++name_request;
		const term = item_name.$input.val() || "";
		const rows = await frappe.db.get_list("Item", {
			fields: ["item_name"],
			filters: [["item_name", "like", `%${term}%`]],
			distinct: true,
			order_by: "item_name asc",
			limit: 30,
		});
		if (sequence !== name_request || term !== item_name.$input.val()) return;
		item_name.set_data(rows.filter(row => row.item_name).map(row => row.item_name));
		if (item_name.$input.is(":focus")) item_name.awesomplete.evaluate();
	}, 200);
	item_name.$input.on("input focus", suggest_names);
	for (const [fieldname, label] of [["item_code", "Item Code"], ["custom_barcode", "Barcode"]]) {
		const control = listview.page.fields_dict[fieldname] || listview.page.add_field({
			fieldname,
			fieldtype: "Data",
			label: __(label),
			condition: "like",
			onchange: () => listview.filter_area.debounced_refresh_list_view(),
		}, wrapper);
		control.$wrapper.show();
	}
	// Keep the two lookup fields beside Item Name, before the other filters.
	const name_field = listview.page.fields_dict.item_name;
	const code = listview.page.fields_dict.item_code;
	const barcode = listview.page.fields_dict.custom_barcode;
	if (name_field) code.$wrapper.insertAfter(name_field.$wrapper);
	barcode.$wrapper.insertAfter(code.$wrapper);
	const scale = listview.page.fields_dict.custom_scale_item || listview.page.add_field({
		fieldname: "custom_scale_item",
		fieldtype: "Check",
		label: __("Scale"),
		default: 0,
		onchange: () => {
			// Saved filters are restored before this toolbar control is created.
			// Remove that duplicate so unchecking also clears a restored selection.
			listview.filter_area.filter_list.get_filter("custom_scale_item")?.remove();
			listview.filter_area.debounced_refresh_list_view();
		},
	}, wrapper);
	const saved_scale = listview.filter_area.filter_list.get_filter("custom_scale_item");
	if (saved_scale?.get_value()[2] === "=" && Number(saved_scale.get_value()[3]) === 1) {
		scale.set_value(1);
	}
	scale.$wrapper.show().insertAfter(barcode.$wrapper);
	arrangeRetailItemFilters(listview);
	listview.page.show_form();



	const original_get_args = listview.get_args.bind(listview);
	listview.get_args = function () {
		const args = original_get_args();
		const value = barcode.get_value()?.trim();
		if (!value) return args;
		const pattern = value.includes("%") ? value : `%${value}%`;
		const raw = barcode.get_value();
		const index = args.filters.findIndex(filter =>
			filter[0] === "Item" && filter[1] === "custom_barcode"
			&& filter[2] === "like" && filter[3] === (raw.includes("%") ? raw : `%${raw}%`)
		);
		if (index < 0) return args;
		args.filters.splice(index, 1);
		args.or_filters = [
			["Item", "custom_barcode", "like", pattern],
			["Item Barcode", "barcode", "like", pattern],
			["Retail Packing Detail", "barcode", "like", pattern],
		];
		args.group_by = "`tabItem`.`name`";
		return args;
	};

	const original_get_count_str = listview.get_count_str.bind(listview);
	listview.get_count_str = function () {
		const args = this.get_args();
		if (!args.or_filters) return original_get_count_str();
		return frappe.call({
			method: "frappe.desk.reportview.get_count",
			args: {
				doctype: "Item",
				filters: args.filters,
				or_filters: args.or_filters,
				distinct: true,
				limit: this.count_upper_bound,
			},
		}).then(({ message: total }) => {
			this.total_count = total;
			this.count_without_children = undefined;
			const count = total === this.count_upper_bound
				? `${format_number(total - 1, null, 0)}+`
				: format_number(total, null, 0);
			return __("{0} of {1}", [format_number(this.data.length, null, 0), count]);
		});
	};
};

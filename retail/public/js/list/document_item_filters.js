// Instance-local filters; native list queries still enforce document permissions.
(() => {
	const itemDoctypes = ["POS Invoice", "Sales Invoice", "Purchase Order", "Purchase Invoice", "Purchase Receipt"];
	const relatedDoctypes = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice",
		"Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Invoice"];
	const doctypes = [...new Set([...itemDoctypes, ...relatedDoctypes])];
	for (const doctype of doctypes) {
		const settings = frappe.listview_settings[doctype] ||= {};
		if (settings.retail_item_filters_installed) continue;
		settings.retail_item_filters_installed = true;
		const onload = settings.onload;
		settings.onload = function (listview) {
			onload?.call(this, listview);
			if (listview.retail_item_filters) return;
			const controls = listview.retail_item_filters = {};
			let clearing = false;
			const refresh = frappe.utils.debounce(() => {
				if (clearing) return;
				listview.start = 0;
				listview.refresh();
			}, 250);
			const fields = itemDoctypes.includes(doctype) ? [["item_code", "Item", "Link", "Item"]] : [];
			if (itemDoctypes.includes(doctype) && doctype !== "Purchase Order") {
				fields.push(["serial_no", "Serial No", "Link", "Serial No"], ["batch_no", "Batch No", "Link", "Batch"]);
			}
			for (const [fieldname, label, fieldtype, options] of fields) {
				controls[fieldname] = frappe.ui.form.make_control({
					parent: listview.filter_area.standard_filters_wrapper,
					df: { fieldname: `retail_filter_${fieldname}`, label: __(label), placeholder: __(label),
						fieldtype, options, only_select: true, ignore_link_validation: fieldname !== "item_code",
						input_class: "input-xs", onchange: () => {
							if (fieldname === "item_code") {
								for (const key of ["serial_no", "batch_no"]) {
									if (controls[key]?.$input) controls[key].$input.cache = {};
									controls[key]?.awesomplete?.close();
								}
							}
							refresh();
						} },
					only_input: true,
				});
				controls[fieldname].refresh();
				controls[fieldname].$wrapper.addClass("col-md-2");
				if (fieldname !== "item_code") {
					controls[fieldname].get_query = () => {
						const item = controls.item_code.get_value();
						return { filters: item ? { [fieldname === "batch_no" ? "item" : "item_code"]: item } : {} };
					};
				}
			}
			if (relatedDoctypes.includes(doctype)) {
				const related = controls.related_document = frappe.ui.form.make_control({
					parent: listview.filter_area.standard_filters_wrapper,
					df: {
						fieldname: "retail_filter_related_document", fieldtype: "Autocomplete",
						label: __("Related Document"), placeholder: __("Related Document"),
						input_class: "input-xs", onchange: refresh,
					},
					only_input: true,
				});
				related.refresh();
				related.$wrapper.addClass("col-md-3");
				related.translate_values = false;
				// Debounce lookups and discard stale responses while the user types.
				related.execute_query_if_exists = frappe.utils.debounce(async function (term) {
					const { message } = await frappe.call({
						method: "retail.related_document_filters.search", args: { txt: term, doctype },
					});
					if (this.$input.is(":focus") && this.$input.val() === term) this.set_data(message || []);
				}, 250);
				related.get_query = () => "retail.related_document_filters.search";
				// Document IDs are text, including when rendered in suggestions.
				related.awesomplete.item = function (item) {
					return $("<li>").attr("aria-selected", "false").text(item.label).get(0);
				};
				related.$input.attr("title", __("Search a document ID, then select its document type and ID."));
			}
			// The native X calls FilterArea.clear; include our instance-local controls.
			const clear = listview.filter_area.clear.bind(listview.filter_area);
			listview.filter_area.clear = async function (...args) {
				clearing = true;
				try {
					for (const control of Object.values(controls)) await control.set_value("");
					return await clear(...args);
				} finally {
					clearing = false;
					listview.start = 0;
					if (args[0] !== false) refresh();
				}
			};
			const values = () => Object.fromEntries(Object.entries(controls)
				.map(([key, control]) => [key, (control.get_value() || "").trim()])
				.filter(([, value]) => value));
			const getArgs = listview.get_args.bind(listview);
			const nativeMethod = listview.method;
			listview.get_args = function () {
				const args = getArgs();
				const filters = values();
				const active = Object.keys(filters).length > 0;
				this.method = active ? "retail.document_item_filters.get" : nativeMethod;
				if (active) args.retail_item_filters = filters;
				return args;
			};
			const getCount = listview.get_count_str.bind(listview);
			listview.get_count_str = async function () {
				const filters = values();
				if (!Object.keys(filters).length) return getCount();
				const { message: total } = await frappe.call({
					method: "retail.document_item_filters.get_count",
					args: { doctype, filters: this.get_filters_for_args(), limit: this.count_upper_bound,
						retail_item_filters: filters },
				});
				this.total_count = total;
				const unique = this.data.uniqBy(row => row.name).length;
				this.count_without_children = unique !== this.data.length ? unique : undefined;
				const count = this.count_upper_bound && total === this.count_upper_bound
					? `${format_number(total - 1, null, 0)}+` : format_number(total, null, 0);
				return __("{0} of {1}", [format_number(unique, null, 0), count]);
			};
			listview.page.show_form();
		};
	}
})();

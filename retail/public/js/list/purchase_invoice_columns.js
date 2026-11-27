// Purchase Invoice defaults matching the purchasing desk layout.
(() => {
	const settings = frappe.listview_settings["Purchase Invoice"] ||= {};
	settings.add_fields = [...new Set([...(settings.add_fields || []),
		"title", "bill_no", "posting_date", "bill_date", "grand_total", "currency"])];
	function fit_filters(view) {
		const controls = {...view.page.fields_dict, ...view.retail_item_filters};
		for (const [name, control] of Object.entries(controls)) {
			if (["company", "title"].includes(name)) { control.$wrapper.hide(); continue; }
			if (!control.$input || !control.$wrapper) continue;
			const placeholder = control.$input.attr("placeholder") || control.df.label || "";
			const width = Math.max(85, placeholder.length * 8 + 38);
			control.$wrapper.css({flex: `0 0 ${width}px`, width: `${width}px`, "min-width": "0", "max-width": "100%"});
		}
	}
	const onload = settings.onload;
	settings.onload = function (view) {
		onload?.call(this, view);
		for (const [fieldname, label, fieldtype] of [
			["bill_no", "Supplier Invoice No", "Data"],
			["bill_date", "Supplier Invoice Date", "Date"],
			["posting_date", "Posting Date", "Date"],
		]) {
			if (view.page.fields_dict[fieldname]) continue;
			view.page.add_field({
				fieldname, label: __(label), placeholder: __(label), fieldtype,
				condition: fieldtype === "Data" ? "like" : "=", is_filter: 1,
				onchange: () => view.filter_area.debounced_refresh_list_view(),
			}, view.filter_area.standard_filters_wrapper);
		}

		fit_filters(view);
		const before_render = settings.before_render;
		settings.before_render = function () {
			before_render?.call(this);
			fit_filters(view);
		};
		if (view.retail_purchase_columns) return;
		view.retail_purchase_columns = true;
		const setup = view.setup_columns;
		view.setup_columns = function () {
			setup.call(this);
			const field = (name, label, width) => ({type: "Field", retail_compact_width: width,
				df: {...frappe.meta.get_docfield(this.doctype, name), fieldname: name, label: __(label)}});
			this.columns = [
				{type: "Subject", df: {fieldname: "name", label: __("ID")}, retail_compact_width: 78},
				field("title", "Title", 270),
				field("bill_no", "Supplier Invoice No", 212),
				field("posting_date", "Posting Date", 142),
				field("bill_date", "Supplier Invoice Date", 199),
				field("grand_total", "Grand Total", 172),
				{type: "Status", retail_compact_width: 94},
			];
			this.retail_fit_columns = true;
			this.retail_fit_saved_columns = true;
			const revision = "purchase-screenshot-v1";
			const key = `retail:list-widths:v1:${frappe.session.user}:Purchase Invoice`;
			try {
				if (localStorage.getItem(key + ":revision") !== revision) {
					this._retail_list_widths = {};
					this._retail_list_order = [];
					localStorage.removeItem(key);
					localStorage.removeItem(key + ":order");
					localStorage.setItem(key + ":revision", revision);
				}
			} catch { /* Defaults also work when browser storage is disabled. */ }
		};
		view.setup_columns();
		view.render_header(true);
	};
})();

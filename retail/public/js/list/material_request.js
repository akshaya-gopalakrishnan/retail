frappe.listview_settings["Material Request"] = frappe.listview_settings["Material Request"] || {};

(function() {
	const VAN_FIELDS = new Set([
		"custom_is_van_stock_request",
		"custom_van_request_type",
		"custom_van_session",
		"custom_van",
		"custom_van_warehouse",
		"custom_driver",
		"custom_driver_name",
	]);

	function isVanStockRequestRoute() {
		const route = frappe.get_route?.() || [];
		const path = window.location.pathname.replace(/\/+$/, "");
		return route[0] === "van-stock-request" || path === "/app/van-stock-request";
	}

	function removeVanFlagFromList(listview) {
		if (isVanStockRequestRoute()) return;
		if (!listview) return;

		if (Array.isArray(listview.filters)) {
			listview.filters = listview.filters.filter((filter) => {
				const fieldname = Array.isArray(filter) ? filter[1] : filter?.fieldname;
				return !VAN_FIELDS.has(fieldname);
			});
		}

		const filterArea = listview.filter_area;
		if (filterArea?.filter_list) {
			filterArea.filter_list = filterArea.filter_list.filter((filter) => !VAN_FIELDS.has(filter?.fieldname));
		}

		if (Array.isArray(listview.columns)) {
			listview.columns = listview.columns.filter((column) => {
				const fieldname = column.df?.fieldname || column.fieldname;
				return !VAN_FIELDS.has(fieldname);
			});
		}

		if (Array.isArray(listview.fields)) {
			listview.fields = listview.fields.filter((fieldname) => !VAN_FIELDS.has(fieldname));
		}

		if (Array.isArray(listview.meta?.fields)) {
			listview.meta.fields = listview.meta.fields.map((df) => {
				if (!VAN_FIELDS.has(df.fieldname)) return df;
				return {
					...df,
					in_standard_filter: 0,
					in_list_view: 0,
					hidden: 1,
				};
			});
		}

		for (const fieldname of VAN_FIELDS) {
			listview.page?.wrapper
				?.find?.(`[data-fieldname="${fieldname}"]`)
				.closest(".filter-field, .list-row-col, .form-group")
				.hide();
		}
	}

	const settings = frappe.listview_settings["Material Request"];
	const previousOnload = settings.onload;
	const previousRefresh = settings.refresh;

	settings.onload = function(listview) {
		previousOnload?.(listview);
		removeVanFlagFromList(listview);
	};

	settings.refresh = function(listview) {
		previousRefresh?.(listview);
		removeVanFlagFromList(listview);
		setTimeout(() => removeVanFlagFromList(listview), 100);
	};
})();

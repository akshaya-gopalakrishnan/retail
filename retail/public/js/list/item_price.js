(() => {
	const settings = frappe.listview_settings["Item Price"] ||= {};
	settings.formatters = {
		...settings.formatters,
		item_code(value) {
			const code = frappe.utils.escape_html(value || "");
			return `<a class="filterable ellipsis" data-filter="item_code,=,${code}" title="${code}">${code}</a>`;
		},
	};
})();

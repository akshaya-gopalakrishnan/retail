/* Instance-scoped column persistence for the explicit Retail form allowlist. */
(() => {
	window.retail = window.retail || {};
	if (retail.column_preferences) return;
	const supported = new Set();

	function save(doctype, key, value) {
		if (!supported.has(doctype) || !["GridView", "RetailScrollableGrid"].includes(key)) {
			return Promise.reject(new Error("Unsupported Retail column preferences"));
		}
		return frappe
			.call({
				method: "retail.column_preferences.save",
				type: "POST",
				args: { doctype, key, value: JSON.stringify(value ?? null) },
			})
			.then((r) => {
				frappe.model.user_settings[doctype] = r.message;
				return r;
			});
	}

	function configureHeader(grid) {
		const row = grid.header_row;
		if (!row || row.__retail_durable_columns || grid.__retail_scroll_options) return;
		row.__retail_durable_columns = true;
		row.update_user_settings_for_grid = function () {
			if (!this.selected_columns_for_grid || !this.frm) return;
			return save(this.frm.doctype, "GridView", {
				[this.grid.doctype]: this.selected_columns_for_grid,
			}).then(() => this.grid.reset_grid());
		};
		row.reset_user_settings_for_grid = function () {
			return save(this.frm.doctype, "GridView", null).then(() => this.grid.reset_grid());
		};
	}

	function enable(frm) {
		for (const control of Object.values(frm.fields_dict)) {
			const grid = control.grid;
			if (!grid || grid.__retail_durable_columns) continue;
			grid.__retail_durable_columns = true;
			const makeHead = grid.make_head;
			grid.make_head = function (...args) {
				const result = makeHead.apply(this, args);
				configureHeader(this);
				return result;
			};
			configureHeader(grid);
		}
	}

	retail.column_preferences = { save, supports: (doctype) => supported.has(doctype) };
	function boot() {
		if (!window.frappe?.ui?.form?.on || !frappe.boot) {
			setTimeout(boot, 100);
			return;
		}
		for (const doctype of frappe.boot.retail_column_doctypes || []) {
			supported.add(doctype);
			frappe.ui.form.on(doctype, { refresh: enable });
		}
	}
	boot();
})();

(() => {
	const settings = frappe.listview_settings["Sales Invoice"] ||= {};
	settings.add_fields = [...new Set([...(settings.add_fields || []), "posting_date"])];
	const onload = settings.onload;
	settings.onload = function (view) {
		onload?.call(this, view);
		if (view.retail_invoice_columns) return;
		view.retail_invoice_columns = true;
		const setup = view.setup_columns;
		view.setup_columns = function () {
			setup.call(this);
			if (!this.columns.some(col => col.df?.fieldname === "posting_date")) {
				this.columns.push({ type: "Field", df: frappe.meta.get_docfield("Sales Invoice", "posting_date") });
			}
			const status = this.columns.filter(column => column.type === "Status" || column.df?.fieldname === "status");
			this.columns = this.columns.filter(column => !status.includes(column)).concat(status);
			this.retail_status_last = true;
			for (const column of this.columns) {
				column.retail_compact_width = column.type === "Status" ? 125
					: column.type === "Subject" ? 125
					: column.df?.fieldname === "posting_date" ? 120
					: column.df?.fieldname === "grand_total" ? 140
					: column.df?.fieldname === "title" ? 160 : 110;
			}
		};
		view.setup_columns();
		view.render_header(true);
	};
})();

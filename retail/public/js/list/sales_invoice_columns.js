(() => {
	const settings = frappe.listview_settings["Sales Invoice"] ||= {};
	settings.add_fields = [...new Set([...(settings.add_fields || []),
		"posting_date", "custom_bill_number", "customer_name", "customer", "due_date"])];
	settings.formatters ||= {};
	settings.formatters.custom_bill_number = (value, df, doc) => frappe.utils.escape_html(value || doc.name || "");
	const onload = settings.onload;
	settings.onload = function (view) {
		onload?.call(this, view);
		const titleFilter = view.page.fields_dict.title;
		if (titleFilter) {
			titleFilter.df.placeholder = __("Bill Number");
			titleFilter.$input?.attr("placeholder", __("Bill Number"));
		}
		if (view.retail_invoice_columns) return;
		view.retail_invoice_columns = true;
		const setup = view.setup_columns;
		view.setup_columns = function () {
			setup.call(this);
			const field = (fieldname, label) => ({type: "Field",
				df: {...frappe.meta.get_docfield("Sales Invoice", fieldname), fieldname, label: __(label)}});
			// Preserve the old Title column's personal position and width.
			const bill = {...field("custom_bill_number", "Bill Number"), identity_field: "title"};
			const detail = [bill, field("customer_name", "Customer"), field("due_date", "Due Date")];
			const columns = [];
			let added = false;
			for (const column of this.columns) {
				const name = column.df?.fieldname;
				if (["title", "custom_bill_number"].includes(name) && column.type !== "Subject") {
					if (!added) columns.push(...detail);
					added = true;
				} else if (!["customer", "customer_name", "due_date"].includes(name)) columns.push(column);
			}
			if (!added) columns.splice(1, 0, ...detail);
			this.columns = columns;
			if (!this.columns.some(col => col.df?.fieldname === "posting_date")) {
				this.columns.push(field("posting_date", "Posting Date"));
			}
			const order = ["name", "custom_bill_number", "customer_name", "posting_date", "due_date", "grand_total", "status"];
			const status = this.columns.find(column => column.type === "Status" || column.df?.fieldname === "status");
			this.columns = order.map(name => name === "status" ? status
				: this.columns.find(column => column.df?.fieldname === name)).filter(Boolean);
			this.retail_status_last = true;
			this.retail_last_field = null;
			if (!this.retail_invoice_order_applied) {
				this.retail_invoice_order_applied = true;
				const key = `retail:list-widths:v1:${frappe.session.user}:Sales Invoice:order`;
				const revision = "bill-customer-posting-due-total-status-v1";
				const current = this.columns.map(column => `${column.type}:${column.identity_field || column.df?.fieldname || column.type}`);
				try {
					if (localStorage.getItem(key + ":revision") !== revision) {
						this._retail_list_order = current;
						localStorage.setItem(key, JSON.stringify(current));
						localStorage.setItem(key + ":revision", revision);
					}
				} catch { this._retail_list_order = current; }
			}
			this.retail_fit_columns = true;
			this.retail_fit_saved_columns = true;
			this.retail_list_activity_width = 70;
			for (const column of this.columns) {
				column.retail_compact_width = column.type === "Status" ? 100
					: column.type === "Subject" ? 90
					: ["posting_date", "due_date"].includes(column.df?.fieldname) ? 110
					: column.df?.fieldname === "grand_total" ? 130
					: column.df?.fieldname === "customer_name" ? 190
					: column.df?.fieldname === "custom_bill_number" ? 130 : 110;
				column.retail_min_width = column.df?.fieldname === "customer_name" ? 120
					: ["posting_date", "due_date"].includes(column.df?.fieldname) ? 90
					: column.df?.fieldname === "custom_bill_number" ? 105 : 70;
			}
		};
		view.setup_columns();
		view.render_header(true);
	};
})();

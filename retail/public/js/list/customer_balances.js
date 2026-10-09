(() => {
	const settings = frappe.listview_settings.Customer ||= {};
	const previous_onload = settings.onload;
	const fields = [
		["credit_limit", "Credit Limit"],
		["outstanding_amount", "Receivable"],
		["unused_credit_note_amount", "Unused Cr.Note"],
		["remaining_credit_limit", "Available Credit"],
	];

	settings.onload = function (listview) {
		previous_onload?.call(this, listview);
		setup_customer_filter(listview);
		setup_credit_filter(listview);
		if (!frappe.model.can_read("Payment Ledger Entry") || listview._credit_columns) return;
		listview._credit_columns = true;
		let generation = 0;
		const escape = frappe.utils.escape_html;
		const note = $('<div class="text-muted small customer-credit-context"></div>')
			.insertBefore(listview.$result);
		const setup_columns = listview.setup_columns;
		listview.setup_columns = function () {
			setup_columns.call(this);
			this.columns.push(...fields.map(([field, label]) => ({
				type: "CustomerCredit", balance_field: field,
				// No DocFields: these display values cannot become SQL filters/sorts.
				df: { label, fieldtype: "Currency" },
			})));
		};
		const get_column_html = listview.get_column_html;
		listview.get_column_html = function (column, doc) {
			if (column.type !== "CustomerCredit") return get_column_html.call(this, column, doc);
			return `<div class="list-row-col hidden-xs ellipsis text-right customer-credit-cell"
				data-customer="${escape(doc.name)}" data-credit-field="${column.balance_field}">—</div>`;
		};
		const render = listview.render;
		listview.render = function () {
			const result = render.apply(this, arguments);
			load_balances(this);
			return result;
		};
		// Let the columns share the available width without a forced scroll area.
		listview.$result.css("overflow-x", "");
		const render_header = listview.render_header;
		listview.render_header = function () {
			const result = render_header.apply(this, arguments);
			size_rows(this);
			return result;
		};
		function size_rows(view) {
			view.$result.find(".list-row, .list-row-head")
				.css("min-width", "0");
			view.$result.find(".list-row-col").css("min-width", "0");
		}
		async function load_balances(view) {
			const request = ++generation;
			size_rows(view);
			const customers = view.data.map((doc) => doc.name);
			if (!customers.length) {
				note.text("");
				return;
			}
			note.text(__("Loading customer credit balances…"));
			try {
				// Load-more lists can exceed one server batch; no request per customer.
				const balances = new Map();
				let context;
				for (let offset = 0; offset < customers.length; offset += 500) {
					const response = await frappe.call({
						method: "retail.customer_balances.get_customer_credit_balances",
						args: { customers: customers.slice(offset, offset + 500) },
					});
					if (request !== generation) return;
					context = response.message;
					for (const row of context.data) balances.set(row.customer, row);
				}
				view.$result.find(".customer-credit-cell").each(function () {
					const row = balances.get(this.dataset.customer);
					if (!row) return;
					const field = this.dataset.creditField;
					const value = field === "remaining_credit_limit" && Number(row.credit_limit) === 0
						? 0 : row[field];
					$(this).html(frappe.format(value, {
						fieldtype: "Currency", options: "currency",
					}, null, { currency: context.currency }));
				});
				note.text("");
			} catch (error) {
				if (request === generation) note.text(__("Customer credit balances unavailable. Check your default Company and accounting permissions."));
			}
		}
		listview.setup_columns();
		listview.render_header(true);
	};

	function setup_customer_filter(listview) {
		if (listview._customer_name_filter) return;
		listview._customer_name_filter = true;
		const page = listview.page;
		const old = page.fields_dict.customer_name;
		const value = old?.get_value() || "";
		old?.$wrapper.remove();
		const customer = page.add_field({
			fieldname: "customer_name", fieldtype: "Autocomplete",
			label: __("Customer Name"), condition: "like", ignore_validation: true,
			onchange: () => listview.filter_area.debounced_refresh_list_view(),
		}, listview.filter_area.standard_filters_wrapper);
		customer.set_input(value);
		let request = 0;
		const suggest = frappe.utils.debounce(async () => {
			const sequence = ++request;
			const term = customer.$input.val() || "";
			try {
				const rows = await frappe.db.get_list("Customer", {
					fields: ["name", "customer_name"],
					filters: [["customer_name", "like", `%${term}%`]],
					order_by: "customer_name asc", limit: 30,
				});
				if (sequence !== request || term !== customer.$input.val()) return;
				customer.set_data(rows.map(row => ({
					value: row.customer_name,
					label: frappe.utils.escape_html(row.customer_name),
					description: frappe.utils.escape_html(row.name),
				})));
				if (customer.$input.is(":focus")) customer.awesomplete.evaluate();
			} catch (error) {
				if (sequence === request) customer.set_data([]);
			}
		}, 200);
		customer.$input.on("input focus", suggest);
	}

	function setup_credit_filter(listview) {
		if (listview._credit_customer_filter) return;
		// Keep the standard filter bookkeeping hidden behind a toolbar toggle button.
		// The string "0" is intentional: it remains a selected value in standard filters.
		const control = listview.page.add_field({
			fieldname: "credit_limit", doctype: "Customer Credit Limit",
			fieldtype: "Select", label: __("Credit Customers"),
			options: [
				{ label: "", value: "" },
				{ label: __("Credit Customers"), value: "0" },
			],
			condition: ">", is_filter: 1,
			onchange: () => {
				const active = control.get_value() === "0";
				button.toggleClass("btn-primary", active).toggleClass("btn-default", !active)
					.attr("aria-pressed", String(active));
				listview.filter_area.debounced_refresh_list_view();
			},
		}, listview.filter_area.standard_filters_wrapper);
		control.$wrapper.hide();
		const button = $('<button type="button" class="btn btn-default btn-sm" aria-pressed="false"></button>')
			.text(__("Credit Customers"))
			.css("border", "1px solid #4ccf62")
			.appendTo(listview.filter_area.standard_filters_wrapper)
			.on("click", () => control.set_value(control.get_value() === "0" ? "" : "0"));
		listview._credit_customer_filter = control;
	}
})();

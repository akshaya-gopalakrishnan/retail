frappe.provide("retail");
frappe.pages = frappe.pages || {};
frappe.pages["van-stock-view"] = frappe.pages["van-stock-view"] || {};

frappe.pages["van-stock-view"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Van Stock View"),
		single_column: true,
	});

	try {
		wrapper.van_stock_view = new retail.VanStockView(page);
	} catch (error) {
		console.error("Unable to render Van Stock View", error);
		$(page.body).html(`<div class="van-stock-empty">${__("Unable to load Van Stock View. Please refresh and try again.")}</div>`);
	}
};

frappe.pages["van-stock-view"].on_page_show = function(wrapper) {
	wrapper.van_stock_view?.refresh();
};

retail.VanStockView = class VanStockView {
	constructor(page) {
		this.page = page;
		this.body = $('<div class="van-stock-view"></div>').appendTo(page.body);
		this.controls = {};
		this.make();
	}

	make() {
		this.filter_area = $('<div class="van-stock-filters"></div>').appendTo(this.body);
		this.make_control("company", "Link", __("Company"), "Company", frappe.defaults.get_default("company"));
		this.make_control("posting_date", "Date", __("As On Date"), null, frappe.datetime.get_today());
		this.make_control("van", "Link", __("Van"), "Van Fleet");
		this.make_control("warehouse", "Link", __("Warehouse"), "Warehouse");
		this.make_control("item_code", "Link", __("Item"), "Item");

		this.refresh_button = $('<button class="btn btn-primary btn-sm">' + __("Refresh") + "</button>")
			.appendTo($('<div></div>').appendTo(this.filter_area))
			.on("click", () => this.refresh(true));

		this.summary_area = $('<div class="van-stock-summary"></div>').appendTo(this.body);
		this.table_area = $('<div></div>').appendTo(this.body);
	}

	make_control(fieldname, fieldtype, label, options, default_value) {
		const field = frappe.ui.form.make_control({
			parent: $('<div></div>').appendTo(this.filter_area),
			df: {
				fieldname,
				fieldtype,
				label,
				options,
				default: default_value,
				change: () => this.refresh(),
			},
			render_input: true,
		});
		field.set_value(default_value || "");
		this.controls[fieldname] = field;
	}

	get_filters() {
		const filters = {};
		Object.keys(this.controls).forEach((fieldname) => {
			const value = this.controls[fieldname].get_value();
			if (value) filters[fieldname] = value;
		});
		return filters;
	}

	refresh(force) {
		clearTimeout(this.refresh_timer);
		this.refresh_timer = setTimeout(() => this.fetch(), force ? 0 : 250);
	}

	fetch() {
		this.refresh_button.prop("disabled", true);
		this.table_area.html(`<div class="van-stock-empty">${__("Loading stock...")}</div>`);

		frappe.call({
			method: "retail.van_stock.get_van_stock_view",
			args: this.get_filters(),
		}).then((response) => {
			const result = response.message || {};
			this.render_summary(result.summary || {});
			this.render_table(result.rows || []);
		}).always(() => {
			this.refresh_button.prop("disabled", false);
		});
	}

	render_summary(summary) {
		const cards = [
			[__("Vans"), summary.vans || 0],
			[__("Warehouses"), summary.warehouses || 0],
			[__("Items"), summary.items || 0],
			[__("Total Qty"), flt(summary.total_qty || 0, 3)],
		];

		this.summary_area.html(cards.map(([label, value]) => `
			<div class="van-stock-summary-card">
				<div class="van-stock-summary-label">${frappe.utils.escape_html(label)}</div>
				<div class="van-stock-summary-value">${frappe.utils.escape_html(String(value))}</div>
			</div>
		`).join(""));
	}

	render_table(rows) {
		if (!rows.length) {
			this.table_area.html(`<div class="van-stock-empty">${__("No stock found for the selected filters.")}</div>`);
			return;
		}

		const html = `
			<div class="van-stock-table-wrap">
				<table class="van-stock-table">
					<thead>
						<tr>
							<th>${__("No.")}</th>
							<th>${__("Van")}</th>
							<th>${__("Warehouse")}</th>
							<th>${__("Item Code")}</th>
							<th>${__("Item Name")}</th>
							<th>${__("UOM")}</th>
							<th class="numeric">${__("Qty")}</th>
							<th class="numeric">${__("Valuation Rate")}</th>
							<th>${__("Last Movement")}</th>
						</tr>
					</thead>
					<tbody>
						${rows.map((row, index) => this.render_row(row, index + 1)).join("")}
					</tbody>
				</table>
			</div>
		`;
		this.table_area.html(html);
	}

	render_row(row, index) {
		const link = (doctype, name, label) => {
			if (!name) return "";
			const text = frappe.utils.escape_html(label || name);
			const href = frappe.router.make_url(["Form", doctype, name]);
			return `<a href="${href}">${text}</a>`;
		};

		return `
			<tr>
				<td>${index}</td>
				<td>${link("Van Fleet", row.van, row.vehicle_name || row.van)}</td>
				<td>${link("Warehouse", row.warehouse)}</td>
				<td>${link("Item", row.item_code)}</td>
				<td>${frappe.utils.escape_html(row.item_name || "")}</td>
				<td>${frappe.utils.escape_html(row.stock_uom || "")}</td>
				<td class="numeric">${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
				<td class="numeric">${frappe.format(row.valuation_rate || 0, { fieldtype: "Currency" })}</td>
				<td>${frappe.utils.escape_html(row.last_movement || "")}</td>
			</tr>
		`;
	}
};

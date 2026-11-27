(function() {
	frappe.provide("retail");
	frappe.pages = frappe.pages || {};
	frappe.standard_pages = frappe.standard_pages || {};

	const van_stock_view_page = {};

	frappe.standard_pages["van-stock-view"] = function() {
		const wrapper = frappe.container.add_page("van-stock-view");
		frappe.pages["van-stock-view"] = wrapper;
		wrapper.on_page_load = van_stock_view_page.on_page_load;
		wrapper.on_page_show = van_stock_view_page.on_page_show;
		wrapper.on_page_load(wrapper);
		$(wrapper).on("show", function() {
			wrapper.on_page_show?.(wrapper);
		});
	};

	van_stock_view_page.on_page_load = function(wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Van Stock View"),
			single_column: false,
		});

		try {
			wrapper.van_stock_view = new retail.VanStockView(page);
		} catch (error) {
			console.error("Unable to render Van Stock View", error);
			$(page.body).html(`<div class="van-stock-empty">${__("Unable to load Van Stock View. Please refresh and try again.")}</div>`);
		}
	};

	van_stock_view_page.on_page_show = function(wrapper) {
		wrapper.van_stock_view?.refresh(true);
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
			

			this.refresh_button = $('<button class="btn btn-primary btn-sm">' + __("Refresh") + "</button>")
				.appendTo($("<div></div>").appendTo(this.filter_area))
				.on("click", () => this.refresh(true));

			this.summary_area = $('<div class="van-stock-summary"></div>').appendTo(this.body);
			this.table_area = $("<div></div>").appendTo(this.body);
		}

		make_control(fieldname, fieldtype, label, options, default_value) {
			const field = frappe.ui.form.make_control({
				parent: $("<div></div>").appendTo(this.filter_area),
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
			const request = this.stock_request = (this.stock_request || 0) + 1;
			this.refresh_button.prop("disabled", true);
			this.table_area.html(`<div class="van-stock-empty">${__("Loading stock...")}</div>`);

			frappe.call({
				method: "retail.van_stock.get_van_stock_summary",
				args: this.get_filters(),
			}).then((response) => {
				if (request !== this.stock_request) return;
				const result = response.message || {};
				this.render_summary(result.summary || {});
				this.render_table(result.rows || []);
			}).catch(() => {
				if (request === this.stock_request) this.table_area.text(__("Unable to load stock. Please try again."));
			}).always(() => {
				if (request === this.stock_request) this.refresh_button.prop("disabled", false);
			});
		}

		render_summary(summary) {
			const cards = [
				[__("Vans"), summary.vans || 0],
				[__("Warehouses"), summary.warehouses || 0],
				[__("Sold Qty (Net)"), flt(summary.sold_qty || 0, 3)],
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
			const esc = frappe.utils.escape_html;
			const num = value => frappe.format(value || 0, {fieldtype: "Float", precision: 3});
			const money = (value, currency) => {
				const formatted = frappe.format(value, {fieldtype: "Currency", options: currency}, {only_value: true});
				return `<span dir="ltr">${esc(formatted).replace(/(-?\d[\d.,]*)/g, '<bdi dir="ltr">$1</bdi>')}</span>`;
			};
			this.table_area.html(
				`<div class="van-stock-table-wrap"><table class="van-stock-table"><thead><tr>${["Van", "Warehouse", "Stock Qty", "Sold Qty (Net)", "Stock Value", "Average Valuation Rate", "Ledger"].map((h, i) => `<th class="${i >= 2 && i <= 5 ? "numeric" : ""}">${__(h)}</th>`).join("")}</tr></thead><tbody>` +
				rows.map((row, i) => `<tr><td>${esc(row.vehicle_name || row.van)}<div class="text-muted">${esc(row.van)}</div></td><td>${esc(row.warehouse)}</td><td class="numeric">${num(row.qty)}</td><td class="numeric">${num(row.sold_qty)}</td><td class="numeric">${money(row.stock_value, row.currency)}</td><td class="numeric">${row.valuation_rate == null ? "—" : money(row.valuation_rate, row.currency)}</td><td><button class="btn btn-xs btn-default" data-ledger="${i}">${__("View Ledger")}</button></td></tr>`).join("") +
				`</tbody></table></div>`);
			if (!rows.length) this.table_area.append(`<div class="van-stock-empty">${__("No vans found for the selected filters.")}</div>`);
			this.table_area.find("[data-ledger]").on("click", event => this.open_ledger(rows[Number(event.currentTarget.dataset.ledger)]));
		}

		open_ledger(van) {
			const esc = frappe.utils.escape_html;
			const filters = this.get_filters();
			const dialog = new frappe.ui.Dialog({title: __("Stock Ledger") + " — " + (van.vehicle_name || van.van), size: "extra-large", fields: [
				{fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("Item"), onchange: () => load(0)},
				{fieldname: "ledger", fieldtype: "HTML"},
			]});
			dialog.$wrapper.addClass("van-stock-ledger-dialog");
			// Keep the Item suggestions closed until the user enters the field.
			dialog.focus_on_first_input = () => {
				dialog.$wrapper.find(".modal-title").attr("tabindex", "-1").trigger("focus");
			};
			dialog.fields_dict.item_code.$input.on("click.vanStockLedger", function () {
				$(this).trigger("input");
			});
			let request = 0;
			const load = async start => {
				const current = ++request;
				const area = dialog.fields_dict.ledger.$wrapper;
				area.html(__("Loading stock movements..."));
				try {
					const result = (await frappe.call({method: "retail.van_stock.get_van_stock_ledger", args: {
						van: van.van, posting_date: filters.posting_date, company: filters.company,
						item_code: dialog.get_value("item_code") || null, start,
					}})).message;
					if (current !== request) return;
					const columns = [
						["posting_date", "Date"], ["posting_time", "Time"], ["item_code", "Item Code"], ["item_name", "Item Name"], ["stock_uom", "UOM"],
						["voucher_no", "Voucher"], ["in_qty", "In Qty"], ["in_rate", "In Rate"], ["in_value", "In Value"],
						["out_qty", "Out Qty"], ["out_rate", "Out Rate"], ["out_value", "Out Value"], ["value_adjustment", "Value Adjustment"],
						["qty_after_transaction", "Balance Qty"], ["valuation_rate", "Valuation Rate"], ["stock_value", "Balance Value"],
					];
					area.html(`<p>${esc(result.warehouse)} · ${esc(result.currency)} · ${__("Balances are per item. Movements through")} ${esc(filters.posting_date || frappe.datetime.get_today())}</p><div class="van-stock-table-wrap"><table class="van-stock-table"><thead><tr>${columns.map((c, i) => `<th class="${i > 5 ? "numeric" : ""}">${__(c[1])}</th>`).join("")}</tr></thead><tbody>${result.rows.map(row => `<tr>${columns.map(([key], i) => {
						if (key === "voucher_no") return `<td><a href="${esc(frappe.router.make_url(["Form", row.voucher_type, row.voucher_no]))}">${esc(row.voucher_type)}: ${esc(row.voucher_no)}</a></td>`;
						const quantity = Number(row[key]) || 0;
						const qty_class = quantity && key === "in_qty" ? "ledger-in-qty" : quantity && key === "out_qty" ? "ledger-out-qty" : "";
						const value = key === "out_qty" && quantity ? -Math.abs(quantity) : row[key];
						return `<td class="${i > 5 ? "numeric" : ""} ${qty_class}">${i > 5 ? frappe.format(value, {fieldtype: "Float", precision: 3}) : esc(String(row[key] || ""))}</td>`;
					}).join("")}</tr>`).join("")}</tbody></table></div>` +
						(!result.rows.length ? `<p>${__("No stock movements found.")}</p>` : "") +
						`<div class="mt-3"><button class="btn btn-default btn-sm ledger-prev" ${!start ? "disabled" : ""}>${__("Previous")}</button> <button class="btn btn-default btn-sm ledger-next" ${!result.has_more ? "disabled" : ""}>${__("Next")}</button></div>`);
					area.find(".ledger-prev").on("click", () => load(Math.max(0, start - 200)));
					area.find(".ledger-next").on("click", () => load(start + 200));
				} catch (error) {
					if (current === request) area.text(__("Unable to load stock movements. Please try again."));
				}
			};
			dialog.show();
			load(0);
		}
	};
})();

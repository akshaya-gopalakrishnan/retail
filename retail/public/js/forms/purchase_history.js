/* Retail-only advisory purchase history. Does not set any transaction fields. */
(() => {
	if (window.retail_purchase_history_registered) return;
	window.retail_purchase_history_registered = true;
	const api = "retail.domains.purchase.history.";
	const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
	const number = (value) => value == null ? "—" : flt(value, 6).toLocaleString(undefined, { maximumFractionDigits: 6 });
	const money = (value, currency) => value == null ? "—" : `${esc(currency)} ${number(value)}`;
	const link = (doctype, name) => name
		? `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}" target="_blank" rel="noopener">${esc(name)}</a>` : "—";
	const parents = ["Purchase Order", "Purchase Receipt", "Purchase Invoice"];

	function snapshot(frm, items = frm.doc.items || []) {
		const doc = {};
		["doctype", "name", "__islocal", "docstatus", "company", "supplier", "currency", "conversion_rate",
			"posting_date", "posting_time", "transaction_date", "is_return", "update_stock"].forEach((key) => doc[key] = frm.doc[key]);
		doc.items = items.map((row) => {
			const item = {};
			["doctype", "name", "idx", "item_code", "item_name", "qty", "custom_foc_qty", "conversion_factor",
				"net_amount", "base_net_amount", "net_rate", "rate", "uom", "stock_uom", "purchase_receipt", "pr_detail", "warehouse"].forEach((key) => item[key] = row[key]);
			return item;
		});
		return doc;
	}

	function setup(frm) {
		if (frm._retail_history) return frm._retail_history;
		const state = frm._retail_history = { comparisons: {}, generation: 0 };
		state.panel = $('<div class="retail-purchase-history-panel mb-3"></div>');
		$('<button type="button" class="btn btn-default btn-sm" aria-haspopup="dialog"></button>')
			.text(__("Purchase Rate Check"))
			.on("click", () => openRateCheck(frm))
			.appendTo(state.panel);
		frm.fields_dict.items.$wrapper.before(state.panel);
		$(frm.wrapper).on("grid-row-render.retail_purchase_history", (_event, gridRow) => {
			if (gridRow.grid.df.fieldname === "items") decorateRow(frm, gridRow);
		});
		return state;
	}

	function openRateCheck(frm) {
		const state = setup(frm);
		if (!state.dialog) {
			state.dialog = new frappe.ui.Dialog({
				title: __("Purchase Rate Check"),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "comparisons" }],
				primary_action_label: __("Close"),
				primary_action: () => state.dialog.hide(),
				secondary_action_label: __("Refresh"),
				secondary_action: () => schedule(frm),
			});
			state.dialog.fields_dict.comparisons.$wrapper.on("click", "[data-history-row]", function () {
				const row = (frm.doc.items || []).find((item) => item.name === this.dataset.historyRow);
				if (row) openHistory(frm, row);
			});
		}
		render(frm);
		state.dialog.show();
		schedule(frm);
	}

	function schedule(frm) {
		const state = setup(frm);
		clearTimeout(state.timer);
		state.generation++;
		render(frm);
		state.timer = setTimeout(() => refresh(frm), 450);
	}

	async function refresh(frm) {
		const state = setup(frm), generation = state.generation;
		state.comparisons = {};
		if (!frm.doc.company || !frm.doc.supplier) {
			state.message = __("Select a company and supplier to compare purchase rates.");
			render(frm);
			return;
		}
		const doc = snapshot(frm), signature = JSON.stringify(doc);
		state.message = __("Checking purchase history…");
		render(frm);
		try {
			// Bound each request while supporting documents with more than 100 rows.
			for (let start = 0; start < doc.items.length; start += 40) {
				const result = await frappe.call({ method: api + "get_comparisons", args: {
					document: { ...doc, items: doc.items.slice(start, start + 40) },
				} });
				if (generation !== state.generation) return;
				if (signature !== JSON.stringify(snapshot(frm))) { schedule(frm); return; }
				state.currency = result.message.currency;
				result.message.rows.forEach((row) => state.comparisons[row.row_name] = row);
			}
			state.message = "";
		} catch (_error) {
			if (generation !== state.generation) return;
			state.message = __("Comparison unavailable. Check your purchase permissions or try Refresh.");
		}
		render(frm);
	}

	function comparisonText(comparison, currency) {
		if (!comparison) return "—";
		if (comparison.is_return) return __("Return — excluded from comparison");
		if (comparison.current_rate == null) return __("Enter quantity, packing and rate to compare");
		if (!comparison.baseline) return comparison.limited_access
			? __("No accessible purchase baseline") : __("No previous purchase from this supplier");
		const label = comparison.higher ? __("Higher purchase rate")
			: Math.abs(comparison.difference) < 0.000001 ? __("Same as previous") : __("Lower than previous");
		const change = comparison.percent == null ? "" : ` (${comparison.percent > 0 ? "+" : ""}${number(comparison.percent)}%)`;
		return `${comparison.higher ? "⚠ " : ""}${label}: ${money(comparison.baseline.rate, currency)} → ${money(comparison.current_rate, currency)}${change}`;
	}

	function decorateRow(frm, gridRow) {
		const comparison = frm._retail_history?.comparisons[gridRow.doc?.name];
		const cell = gridRow.columns?.rate;
		if (cell) {
			cell.toggleClass("text-danger", Boolean(comparison?.higher));
			cell.css("box-shadow", comparison?.higher ? "inset 3px 0 var(--red-500, #c92a2a)" : "");
		}
		gridRow.wrapper.find(".retail-row-history").remove();

	}

	function render(frm) {
		const state = setup(frm);
		(frm.fields_dict.items.grid.grid_rows || []).forEach((row) => decorateRow(frm, row));
		if (!state.dialog) return;
		const rows = (frm.doc.items || []).filter((row) => row.item_code);
		let html = rows.length ? "" : `<p class="text-muted">${__("Add an item to check purchase rates.")}</p>`;
		if (frm.doc.doctype === "Purchase Invoice" && rows.some((row) => !row.purchase_receipt)) {
			html += `<div class="text-muted small mb-3">${__("Standalone invoice: Retail automatically enables Update Stock for stock items when no stock-item row is linked to a Purchase Receipt. If these goods were entered as opening stock or a Stock Entry, review earlier stock movements before submitting to avoid receiving them twice.")}</div>`;
		}
		if (rows.length && state.message) html += `<p class="text-muted">${esc(state.message)}</p>`;
		if (rows.length) html += `<div class="table-responsive"><table class="table table-sm mb-0"><thead><tr>
			<th>${__("Item")}</th><th>${__("Net / stock unit")}</th><th>${__("Rate check")}</th><th></th></tr></thead><tbody>${rows.map((row) => {
			const comparison = state.comparisons[row.name];
			const baseline = comparison?.baseline;
			const basis = baseline ? `<div class="text-muted small">${esc(baseline.date)} · ${esc(__(baseline.rate_basis))} · ${link(baseline.doctype, baseline.name)}</div>` : "";
			const receipt = comparison?.linked_receipt;
			const receiptInfo = receipt ? `<div class="text-muted small">${__("Goods received")}: ${link("Purchase Receipt", receipt.name)} · ${__("Receipt net / unit")}: ${money(receipt.comparable_rate, state.currency)} · ${__("Bill net / unit")}: ${money(comparison.current_rate, state.currency)}</div>` : "";
			return `<tr><td>${esc(row.idx)}. ${esc(row.item_code)}</td><td>${money(comparison?.current_rate, state.currency)} / ${esc(row.stock_uom || row.uom)}</td>
				<td><span class="${comparison?.higher ? "text-danger font-weight-bold" : "text-muted"}">${comparisonText(comparison, state.currency)}</span>${basis}${receiptInfo}</td>
				<td><button type="button" class="btn btn-xs btn-default" data-history-row="${esc(row.name)}">${__("Purchase History")}</button></td></tr>`;
		}).join("")}</tbody></table></div>`;
		state.dialog.fields_dict.comparisons.$wrapper.html(html);
	}

	function detailRow(row, currency) {
		return `<tr><td>${link(row.doctype, row.name)}<div class="text-muted small">${esc(row.doctype)} · ${esc(row.posting_date)}</div></td>
			<td>${number(row.qty)} ${esc(row.uom)}${flt(row.custom_foc_qty) ? `<div class="text-muted small">+ ${number(row.custom_foc_qty)} ${__("free")}</div>` : ""}</td>
			<td>${money(row.rate, row.currency)}<div class="text-muted small">${__("Discount")}: ${number(row.discount_percentage)}% / ${money(row.discount_amount, row.currency)}</div></td>
			<td>${money(row.net_rate, row.currency)}</td><td>${money(row.comparable_rate, currency)} / ${esc(row.stock_uom)}
			</td></tr>`;
	}

	function historyHtml(data) {
		let html = data.limited_access ? `<div class="text-muted small mb-3">${__("Some purchase document types or cost fields are not accessible. History and billing status may be incomplete.")}</div>` : "";
		if (data.latest.length) html += `<div class="mb-3"><strong>${__("Latest comparable rates")}</strong>${data.latest.map((row) =>
			`<div>${esc(row.supplier)}: <strong>${money(row.rate, data.currency)} / ${esc(row.stock_uom)}</strong> <span class="text-muted small">· ${esc(row.date)} · ${esc(__(row.basis))}</span></div>`).join("")}</div>`;
		if (!data.rows.length) return html + `<p class="text-muted">${__("No accessible purchases in this date range.")}</p>`;
		return html + data.rows.map((chain) => {
			const records = [...(chain.receipt ? [chain.receipt] : []), ...chain.invoices];
			return `<div class="border rounded p-3 mb-3"><div class="d-flex justify-content-between"><strong>${esc(chain.supplier_name || chain.supplier)}</strong>
				<span class="indicator-pill ${chain.is_return ? "orange" : chain.invoices.length ? "blue" : "gray"}">${esc(__(chain.status))}</span></div>
				<div class="my-2"><span class="text-muted">${esc(__(chain.rate_basis))}:</span> <strong>${money(chain.rate, data.currency)} / ${esc(chain.stock_uom)}</strong>
				</div>
				<div class="table-responsive"><table class="table table-sm"><thead><tr><th>${__("Document")}</th><th>${__("Quantity / pack")}</th>
				<th>${__("Entered rate / discount")}</th><th>${__("Net / pack")}</th><th>${__("Effective net / stock unit")}</th></tr></thead>
				<tbody>${records.map((row) => detailRow(row, data.currency)).join("")}</tbody></table></div></div>`;
		}).join("");
	}

	function openHistory(frm, row) {
		if (!frm.doc.company || !frm.doc.supplier) {
			frappe.msgprint(__("Select a company and supplier first."));
			return;
		}
		const doc = snapshot(frm);
		let scope = "supplier", start = 0, request = 0;
		const dialog = new frappe.ui.Dialog({
			title: `${__("Purchase History")} — ${row.item_code}`, size: "extra-large",
			fields: [
				{ fieldtype: "Date", fieldname: "from_date", label: __("From date"), default: frappe.datetime.add_months(frappe.datetime.get_today(), -1) },
				{ fieldtype: "Column Break" },
				{ fieldtype: "Date", fieldname: "to_date", label: __("To date"), default: frappe.datetime.get_today() },
				{ fieldtype: "Section Break" },
				{ fieldtype: "HTML", fieldname: "history" },
			],
			primary_action_label: __("Close"), primary_action: () => dialog.hide(),
		});
		const wrapper = dialog.fields_dict.history.$wrapper;
		["from_date", "to_date"].forEach((fieldname) => {
			dialog.fields_dict[fieldname].df.onchange = () => { start = 0; load(); };
		});
		function tabs() {
			return `<div class="btn-group mb-3" role="tablist"><button type="button" role="tab" aria-selected="${scope === "supplier"}" class="btn btn-sm ${scope === "supplier" ? "btn-primary" : "btn-default"}" data-scope="supplier">${__("This Supplier")}</button>
				<button type="button" role="tab" aria-selected="${scope === "others"}" class="btn btn-sm ${scope === "others" ? "btn-primary" : "btn-default"}" data-scope="others">${__("Other Suppliers")}</button></div>`;
		}
		async function load() {
			const current = ++request;
			wrapper.html(tabs() + `<p class="text-muted">${__("Loading…")}</p>`);
			try {
				const { message: data } = await frappe.call({ method: api + "get_history", args: {
					document: doc, item_code: row.item_code, scope, start,
					from_date: dialog.get_value("from_date"), to_date: dialog.get_value("to_date"),
				} });
				if (current !== request) return;
				wrapper.html(tabs() + historyHtml(data) + `<div class="d-flex justify-content-between align-items-center"><button type="button" class="btn btn-default btn-sm" data-page="previous" ${start === 0 ? "disabled" : ""}>${__("Previous")}</button>
					<span>${data.total ? start + 1 : 0}–${Math.min(start + data.page_length, data.total)} / ${data.total}</span>
					<button type="button" class="btn btn-default btn-sm" data-page="next" ${start + data.page_length >= data.total ? "disabled" : ""}>${__("Next")}</button></div>
					<hr><button type="button" class="btn btn-default btn-sm" data-stock-context>${__("Earlier Stock Entries / Opening Stock")}</button><div data-stock-results class="mt-2 text-muted small"></div>`);
			} catch (_error) {
				if (current === request) wrapper.html(tabs() + `<p class="text-danger">${__("Unable to load history. Check permissions and try again.")}</p>`);
			}
		}
		wrapper.on("click", "[data-scope]", function () { scope = this.dataset.scope; start = 0; load(); });
		wrapper.on("click", "[data-page]", function () { start += this.dataset.page === "next" ? 20 : -20; load(); });
		wrapper.on("click", "[data-stock-context]", async function () {
			const target = wrapper.find("[data-stock-results]");
			target.text(__("Loading…"));
			try {
				const { message: entries } = await frappe.call({ method: api + "get_stock_context", args: { document: doc, item_code: row.item_code } });
				target.html((entries.length ? entries.map((entry) => `<div>${link(entry.doctype, entry.name)} · ${esc(entry.doctype)} · ${esc(entry.posting_date)}</div>`).join("") : esc(__("No accessible earlier entries found."))));
			} catch (_error) { target.text(__("Unable to load stock movements.")); }
		});
		dialog.show();
		load();
	}

	parents.forEach((doctype) => {
		const events = {};
		["refresh", "supplier", "company", "currency", "conversion_rate", "posting_date", "posting_time", "transaction_date",
			"discount_amount", "additional_discount_percentage", "apply_discount_on", "taxes_and_charges", "update_stock",
			"net_total", "base_net_total", "total_taxes_and_charges"].forEach((event) => events[event] = schedule);
		frappe.ui.form.on(doctype, events);
		const childEvents = {};
		["item_code", "qty", "custom_foc_qty", "uom", "conversion_factor", "rate", "net_rate", "net_amount", "base_net_amount", "discount_percentage",
			"discount_amount", "price_list_rate", "item_tax_template", "purchase_receipt", "custom_rate_including_vat",
			"custom_rate_exclusive_vat", "items_add", "items_remove"].forEach((event) => childEvents[event] = schedule);
		frappe.ui.form.on(`${doctype} Item`, childEvents);
	});
	const taxEvents = {};
	["rate", "tax_amount", "included_in_print_rate", "charge_type", "taxes_add", "taxes_remove"].forEach((event) => {
		taxEvents[event] = (frm) => { if (parents.includes(frm.doctype)) schedule(frm); };
	});
	frappe.ui.form.on("Purchase Taxes and Charges", taxEvents);
})();

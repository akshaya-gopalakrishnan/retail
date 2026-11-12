/* Purchase-only packing grid, using the Link control's keyboard navigation. */
(() => {
	window.retail = window.retail || {};
	const esc = value => frappe.utils.escape_html(String(value ?? ""));
	const columns = values => `<span class="retail-packing-cells">${values.map(value => `<span>${esc(value)}</span>`).join("")}</span>`;
	function standardOptions(control, args) {
		const options = [];
		const formatted = control.df.filter_description || (args.filters && control.get_filter_description(structuredClone(args.filters)));
		const description = formatted && window.strip_html(formatted);
		if (description) options.push({value: "filters__link_option", label: description,
			html: `<span class="text-muted">${esc(description)}</span>`, action() {}});
		if (!control.df.only_select) {
			if (frappe.model.can_create("Item")) options.push({value: "create_new__link_option",
				label: __("Create a new {0}", [__("Item")]), action: control.new_doc});
			options.push(...(frappe.ui.form.ControlLink.link_options?.(control) || []));
			if (locals.DocType) options.push({value: "advanced_search__link_option",
				label: __("Advanced Search"), action: control.open_advanced_search});
		}
		return options;
	}

	function bind(control, select) {
		if (!control?.awesomplete || control.__retail_packing_search) return;
		control.__retail_packing_search = true;
		const awesome = control.awesomplete;
		$(awesome.ul).addClass("retail-packing-results");
		awesome.item = function (item, _value, index) {
			const result = this.get_item(item.value);
			const choice = result.packing;
			if (!choice) return $("<li role='option'>").html(result.html || esc(result.label || result.value)).get(0);
			const option = $("<li role='option'>").html(columns([
				choice.item_name, choice.packing_name || choice.item_name,
				choice.barcode, choice.packing_uom, choice.conversion_factor,
			])).attr("title", choice.item_code);
			if (index === 0) $("<div class='retail-packing-heading'>").html(columns([
				__("Item Name"), __("Packing Name"), __("Barcode"), __("UOM"), __("UOM Factor"),
			])).on("mousedown click", event => { event.preventDefault(); event.stopPropagation(); }).prependTo(option);
			return option.get(0);
		};
		let request = 0;
		let timer;
		const pageSize = 20;
		async function loadPage(txt, args, version, existing = []) {
			try {
				const {message} = await frappe.call({
					method: "retail.domains.purchase.packing_search.search", args: {
						txt, start: existing.length, page_length: pageSize + 1,
						filters: args.filters, query: args.query,
						reference_doctype: control.get_reference_doctype(),
					}, no_spinner: true,
				});
				if (version !== request || !control.$input.is(":focus")) return;
				const rows = message || [];
				const allRows = existing.concat(rows.slice(0, pageSize));
				// Match native Link search: the permission-checked result already
				// contains the Item title, so selection need not fetch it again.
				for (const packing of allRows) frappe.utils.add_link_title?.("Item", packing.item_code, packing.item_name);
				const choices = allRows.map(packing => ({
					value: JSON.stringify([packing.item_code, packing.packing_id]),
					label: packing.item_name, packing,
				}));
				if (rows.length > pageSize) choices.push({
					value: "load_more__retail_packing", label: __("Load more results"),
					action() {
						const next = ++request;
						control.$input.trigger("focus");
						loadPage(txt, args, next, allRows);
					},
				});
				choices.push(...standardOptions(control, args));
				awesome.maxItems = choices.length;
				awesome.list = choices;
			} catch (error) {
				if (version === request) awesome.close();
				console.error(error);
			}
		}
		control.$input[0].addEventListener("keydown", event => {
			if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || event.isComposing) return;
			if (!["Enter", "Tab"].includes(event.key) || !awesome.opened || !awesome.selected) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			awesome.select(undefined, undefined, event);
		}, true);
		control.$input.off("input").on("input.retailPacking", () => {
			clearTimeout(timer);
			const version = ++request;
			const txt = control.$input.val();
			// Never leave choices for the previous search selectable during a request.
			awesome.close();
			awesome.list = [];
			timer = setTimeout(() => {
				const args = {};
				control.set_custom_query(args);
				loadPage(txt, args, version);
			}, 200);
		});
		control.$input.off("awesomplete-select").on("awesomplete-select.retailPacking", event => {
			const result = awesome.get_item(event.originalEvent.text.value);
			const choice = result?.packing;
			event.preventDefault();
			if (control.__retail_packing_busy) return;
			++request;
			clearTimeout(timer);
			awesome.close();
			if (!choice) {
				result?.action?.call(control);
				return;
			}
			control.set_input(choice.item_code);
			control.__retail_packing_busy = true;
			Promise.resolve().then(() => select(choice)).catch(error => console.error(error))
				.finally(() => { control.__retail_packing_busy = false; });
		});
	}
	function installScanner(frm) {
		const scanner = frm.cscript?.barcode_scanner;
		if (!scanner || scanner.__retail_packing_input) return;
		scanner.__retail_packing_input = true;
		const pending = new Map();
		const update = scanner.update_table;
		const setBarcode = scanner.set_barcode;
		const enabled = () => frm.doc.docstatus === 0 && !frm.doc.is_return && !frm.doc.is_internal_supplier;
		const applyScan = async function (data, ...args) {
			if (!enabled() || !data?.barcode || !data.item_code || !data.uom) return update.call(this, data, ...args);
			const key = data.barcode;
			let entry = pending.get(key);
			if (!entry) { entry = {...data, count: 0}; pending.set(key, entry); }
			entry.count++;
			try {
				return await update.call(this, data, ...args);
			} finally {
				if (--entry.count === 0) pending.delete(key);
			}
		};
		// Native scans mutate the same rows asynchronously. Process each result
		// in order so a rapid second scan sees the first scan's completed quantity.
		let queue = Promise.resolve();
		scanner.update_table = function (data, ...args) {
			if (!enabled()) return update.call(this, data, ...args);
			const action = queue.then(async () => {
				frm.__retail_purchase_scan_active = true;
				clearTimeout(frm.__retail_purchase_focus_timer);
				try {
					return await applyScan.call(this, data, ...args);
				} finally {
					frm.__retail_purchase_scan_active = false;
					if (window.cur_frm === frm && !$(".modal:visible").length) {
						frm.fields_dict.scan_barcode?.set_focus();
					}
				}
			});
			queue = action.catch(() => {});
			return action;
		};
		scanner.set_barcode = async function (row, barcode, ...args) {
			const data = pending.get(barcode);
			if (!enabled() || !data) return setBarcode.call(this, row, barcode, ...args);
			const previousUom = row.uom;
			if (!row.item_code) row.uom = data.uom;
			try {
				return await setBarcode.call(this, row, barcode, ...args);
			} catch (error) {
				if (!row.item_code) row.uom = previousUom;
				throw error;
			}
		};
	}
	window.retail.purchase_packing_search = {bind, installScanner};

	if (!document.getElementById("retail-packing-search-style")) {
		$("<style id='retail-packing-search-style'>").text(`
			.awesomplete > ul.retail-packing-results { width: min(560px, 90vw); min-width: min(560px, 90vw); max-width: 90vw; max-height: 360px; overflow: auto; }
			body .awesomplete > ul.retail-packing-results > li:hover { background: #c6ddf6 !important; color: #102a43 !important; }
			.retail-packing-cells { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1.5fr) minmax(0, 1.2fr) minmax(0, .7fr) minmax(0, .6fr); gap: 6px; padding: 4px; }
			.retail-packing-cells > span { min-width: 0; white-space: normal; overflow-wrap: anywhere; }
			.retail-packing-heading { background: var(--fg-color); color: var(--text-color); font-weight: 600; border-bottom: 1px solid var(--border-color); }
		`).appendTo(document.head);
	}

	for (const doctype of ["Purchase Receipt", "Purchase Invoice"]) frappe.ui.form.on(doctype, {
		scan_barcode: installScanner,
		refresh(frm) {
			installScanner(frm);
			if (frm.__retail_packing_focus) return;
			frm.__retail_packing_focus = true;
			frm.wrapper.addEventListener("focus", event => {
				const input = event.target;
				if (!input.matches('[data-fieldname="item_code"] input, [data-fieldname="item_name"] input')) return;
				if (frm.doc.docstatus !== 0 || frm.doc.is_return || !frm.perm?.[0]?.write) return;
				const grid = frm.fields_dict.items?.grid;
				const rowName = $(input).closest(".grid-row").attr("data-name");
				const gridRow = grid?.grid_rows_by_docname?.[rowName];
				const control = [gridRow?.on_grid_fields_dict?.item_code, gridRow?.on_grid_fields_dict?.item_name,
					gridRow?.grid_form?.fields_dict?.item_code]
					.find(field => field?.$input?.[0] === input && field.df.options === "Item");
				window.retail.purchase_packing_search.bind(control, async choice => {
					const row = gridRow.doc;
					// Match native barcode entry and Quick Entry: an empty row can
					// supply its selected packing to the initial native item lookup.
					// Existing rows keep their normal item/UOM transition behavior.
					const seed = !row.item_code && choice.barcode && !frm.doc.is_internal_supplier;
					const previous = {uom: row.uom, barcode: row.barcode};
					if (seed) Object.assign(row, {uom: choice.uom, barcode: choice.barcode});
					try {
						await control.set_value(choice.item_code);
					} catch (error) {
						if (seed && !row.item_code) Object.assign(row, previous);
						throw error;
					}
					while (row.__retail_vat_syncing || row.__retail_sell_price_syncing) await new Promise(resolve => setTimeout(resolve, 16));
					await frappe.model.set_value(row.doctype, row.name, "uom", choice.uom);
					row.barcode = choice.barcode || "";
					row.custom_item_barcode = choice.barcode || "";
					frm.dirty();
					frm.refresh_field("items");
				});
			}, true);
		},
	});
})();

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
		scanner.update_table = async function (data, ...args) {
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

	const purchaseParents = ["Purchase Receipt", "Purchase Invoice"];
	const detailSkip = new Set(["name", "idx", "doctype", "parent", "parentfield", "parenttype", "owner", "creation", "modified", "docstatus"]);

	function lineEligible(frm) {
		return purchaseParents.includes(frm?.doc?.doctype) && Number(frm.doc.docstatus || 0) === 0
			&& !frm.doc.is_return && !frm.doc.is_internal_supplier;
	}

	function lineCandidates(frm, scan) {
		const uom = scan?.uom;
		if (!scan?.item_code || !uom) return [];
		return (frm.doc.items || []).filter(row => row.item_code === scan.item_code && row.uom === uom
			&& !row.custom_foc_parent && !row.serial_and_batch_bundle && !flt(row.rejected_qty)
			&& (row.warehouse || "") === (frm.doc.set_warehouse || "")
			&& (!scan.batch_no || !row.batch_no || row.batch_no === scan.batch_no));
	}

	function lineMatch(frm, scan) {
		const rows = lineCandidates(frm, scan);
		return rows.length === 1 ? rows[0] : null;
	}

	function blankRow(frm) {
		// A new Purchase Receipt or Invoice already has one empty item row.
		// Filling that row keeps the item on row 1.
		return (frm.doc.items || []).find(row => !row.item_code && !row.custom_foc_parent) || null;
	}

	function money(value) {
		return flt(value, 2);
	}

	function applyVatDisplay(row, vatRate) {
		if (!frappe.meta.has_field(row.doctype, "custom_rate_including_vat")) return;
		const rate = flt(row.rate);
		const qty = flt(row.qty);
		const inclusive = money(rate * (1 + flt(vatRate) / 100));
		row.custom_rate_including_vat = inclusive;
		if (frappe.meta.has_field(row.doctype, "custom_amount_including_vat")) {
			row.custom_amount_including_vat = money(qty * inclusive);
		}
		if (frappe.meta.has_field(row.doctype, "custom_vat_amount")) {
			row.custom_vat_amount = money(qty * rate * flt(vatRate) / 100);
		}
	}

	function applySelling(row, scan) {
		if (!frappe.meta.has_field(row.doctype, "custom_cur_sell_rate")) return;
		const current = flt(scan.selling_rate);
		row.custom_cur_sell_rate = current;
		if (row.custom_upd_sell_price && !flt(row.custom_new_sell_rate)) row.custom_new_sell_rate = current;
		const exclusive = flt(row.custom_new_sell_rate || row.custom_cur_sell_rate);
		if (frappe.meta.has_field(row.doctype, "custom_new_sell_incl")) {
			row.custom_new_sell_incl = money(exclusive * (1 + flt(scan.selling_vat_rate) / 100));
		}
		if (!frappe.meta.has_field(row.doctype, "custom_sell_margin")) return;
		const purchase = flt(row.rate || row.net_rate);
		const selling = flt(row.custom_new_sell_rate || row.custom_cur_sell_rate);
		const margin = selling ? selling - purchase : 0;
		row.custom_sell_margin = money(margin);
		row.custom_sell_margin_pct = selling ? flt(margin / selling * 100, 3) : 0;
	}

	function applyVatTax(frm, setup) {
		if (!setup) return;
		const managed = row => String(row?.description || "").trim().startsWith("Purchase Tax [");
		(frm.doc.taxes || []).filter(managed).forEach(row => frappe.model.clear_doc(row.doctype, row.name));
		frm.doc.taxes = (frm.doc.taxes || []).filter(row => !managed(row));
		(setup.tax_rows || []).forEach(values => Object.assign(frm.add_child("taxes"), values));
		Object.entries(setup.item_tax_rates || {}).forEach(([name, itemTaxRate]) => {
			const item = (frm.doc.items || []).find(row => row.name === name);
			if (item && item.item_tax_rate !== undefined) item.item_tax_rate = itemTaxRate || "{}";
		});
		frm.refresh_field("taxes");
	}

	function rememberItem(frm, item) {
		if (!item?.name) return;
		const state = frm.__retail_purchase_tracking ||= {items: new Map(), generation: 0};
		state.items.set(item.name, item);
	}

	function rememberBarcode(frm, barcode, row) {
		if (!barcode || !row?.name) return;
		(frm.__retail_barcode_rows ||= new Map()).set(barcode, row.name);
	}

	function cachedRow(frm, barcode) {
		const name = frm.__retail_barcode_rows?.get(barcode);
		return (frm.doc.items || []).find(row => row.name === name && row.item_code) || null;
	}

	function finishLine(frm) {
		try {
			frm.cscript?.calculate_taxes_and_totals?.();
		} catch (error) {
			console.error(error);
		}
		frm.dirty?.();
		frm.refresh_field("items");
	}

	function stockFields(row) {
		row.stock_qty = flt(flt(row.qty) * flt(row.conversion_factor || 1));
		if (frappe.meta.has_field(row.doctype, "custom_total_stock_qty")) {
			row.custom_total_stock_qty = flt(row.qty) + flt(row.custom_foc_qty);
		}
	}

	function bump(frm, row, scan = {}) {
		if (scan.serial_no && String(row.serial_no || "").split(/\s*\n\s*/).includes(scan.serial_no)) {
			frappe.throw(__("This serial number is already in the receipt."));
		}
		const previous = flt(row.qty);
		// One scan is one unit. A quantity equal to the barcode is the wedge
		// typing into the row, not a quantity to add.
		const barcode = String(scan.barcode || scan.search_value || "").trim();
		const requested = flt(scan.qty);
		const increment = requested > 0 && String(Math.round(requested)) !== barcode ? requested : 1;
		row.qty = previous + increment;
		if (row.received_qty != null && flt(row.received_qty) === previous) row.received_qty = row.qty;
		stockFields(row);
		row.amount = money(flt(row.qty) * flt(row.rate));
		if (row.custom_rate_including_vat != null && frappe.meta.has_field(row.doctype, "custom_amount_including_vat")) {
			row.custom_amount_including_vat = money(flt(row.qty) * flt(row.custom_rate_including_vat));
		}
		if (previous && row.custom_vat_amount != null) {
			row.custom_vat_amount = money(flt(row.custom_vat_amount) / previous * flt(row.qty));
		}
		if (scan.serial_no) {
			row.serial_no = [...new Set(`${row.serial_no || ""}\n${scan.serial_no}`.split(/\s*\n\s*/).filter(Boolean))].join("\n");
		}
		if (scan.batch_no && !row.batch_no) row.batch_no = scan.batch_no;
		if (barcode) {
			row.barcode = barcode;
			row.custom_item_barcode = barcode;
			rememberBarcode(frm, barcode, row);
		}
		finishLine(frm);
		return row;
	}

	function applyLine(frm, row, scan) {
		const details = scan.details || {};
		for (const [key, value] of Object.entries(details)) {
			if (!detailSkip.has(key) && value != null) row[key] = value;
		}
		row.item_code = scan.item_code;
		row.uom = details.uom || scan.uom || row.uom;
		row.qty = flt(scan.qty || row.qty) || 1;
		// get_item_details leaves rate at 0 and puts the Item Master / price-list
		// price in price_list_rate. The rate columns read rate, so copy it across
		// before the VAT display is calculated.
		if (!flt(row.rate) && flt(row.price_list_rate)) {
			const list = flt(row.price_list_rate);
			const margin = row.margin_type === "Percentage"
				? list * flt(row.margin_rate_or_amount) / 100
				: flt(row.margin_rate_or_amount);
			const withMargin = list + margin;
			const discounted = flt(row.discount_amount) > 0
				? withMargin - flt(row.discount_amount)
				: withMargin * (1 - flt(row.discount_percentage) / 100);
			const digits = typeof precision === "function" ? precision("rate", row) : 2;
			row.rate_with_margin = flt(withMargin, digits);
			row.rate = flt(discounted, digits);
		}
		if (frm.doc.set_warehouse) row.warehouse = frm.doc.set_warehouse;
		const barcode = scan.barcode || scan.search_value || details.barcode || "";
		if (barcode) {
			row.barcode = barcode;
			row.custom_item_barcode = barcode;
			rememberBarcode(frm, barcode, row);
		}
		if (scan.batch_no) row.batch_no = scan.batch_no;
		if (scan.serial_no) row.serial_no = scan.serial_no;
		const item = scan.item || {};
		if (item.has_serial_no || item.has_batch_no) row.use_serial_batch_fields = 1;
		rememberItem(frm, item);
		stockFields(row);
		if (row.rate != null) row.amount = money(flt(row.qty) * flt(row.rate));
		applyVatDisplay(row, scan.purchase_vat_rate);
		applySelling(row, scan);
		const gridRow = frm.fields_dict?.items?.grid?.grid_rows_by_docname?.[row.name];
		for (const field of ["custom_cur_sell_rate", "custom_new_sell_rate", "custom_new_sell_incl", "custom_sell_margin", "custom_sell_margin_pct"]) {
			gridRow?.refresh_field?.(field);
		}
		try {
			applyVatTax(frm, scan.vat_tax);
		} catch (error) {
			console.error(error);
		}
		if (row.item_name) frappe.utils.add_link_title?.("Item", row.item_code, row.item_name);
		if (Array.isArray(row.free_item_data) && row.free_item_data.length) frm.cscript?.apply_product_discount?.(row);
		finishLine(frm);
		// Column visibility and the advisory rate check read the row after it is filled.
		// They must not run the native item_code pricing chain.
		frm.script_manager?.trigger?.("items_add", row.doctype, row.name);
		return row;
	}

	function discardRow(frm, row) {
		if (!row || row.item_code) return;
		frappe.model.clear_doc(row.doctype, row.name);
		frm.doc.items = (frm.doc.items || []).filter(item => item.name !== row.name);
	}

	async function fill(frm, scan, target) {
		if (scan?.item_code && !scan.uom && !target?.item_code) {
			const same = (frm.doc.items || []).filter(row => row.item_code === scan.item_code
				&& !row.custom_foc_parent && !row.serial_and_batch_bundle && !flt(row.rejected_qty));
			if (same.length === 1) scan = Object.assign({}, scan, {uom: same[0].uom});
		}
		const barcode = scan?.barcode || scan?.search_value;
		if (!target?.item_code) {
			const known = scan?.item_code && scan?.uom ? lineMatch(frm, scan) : null;
			if (known) return {row: bump(frm, known, scan), bumped: true, item: scan.item};
			if (!scan?.item_code && barcode) {
				const cached = cachedRow(frm, barcode);
				if (cached) return {row: bump(frm, cached, scan), bumped: true};
			}
		}
		let row = target && (frm.doc.items || []).includes(target) ? target : null;
		let created = false;
		if (!row?.item_code) row = row || blankRow(frm);
		if (!row) {
			row = frm.add_child("items");
			created = true;
		}
		try {
			const {message} = await frappe.call({
				method: "retail.domains.purchase.line_fill.fill_line",
				args: {
					doc: frm.doc,
					item_code: scan.item_code,
					barcode: scan.barcode,
					uom: scan.uom,
					search_value: scan.search_value,
					child_name: row.name,
					qty: flt(row.qty) || flt(scan.qty) || 1,
				},
			});
			if (message?.warehouse && !message.item_code) {
				if (created) discardRow(frm, row);
				return {warehouse: message.warehouse};
			}
			if (message?.scale_barcode_type) {
				frappe.throw(__("Use the full {0} for this scale barcode.", [frm.doc.doctype]));
			}
			if (!message?.item_code) {
				if (created) discardRow(frm, row);
				return null;
			}
			const resolved = Object.assign({}, scan, message);
			if (resolved.serial_no && (frm.doc.items || []).some(other => other !== row
				&& String(other.serial_no || "").split(/\s*\n\s*/).includes(resolved.serial_no))) {
				frappe.throw(__("This serial number is already in the receipt."));
			}
			const elsewhere = !row.item_code && lineMatch(frm, {
				item_code: resolved.item_code,
				uom: resolved.uom || message.details?.uom,
				batch_no: resolved.batch_no,
			});
			if (elsewhere && elsewhere !== row) {
				if (created) discardRow(frm, row);
				return {row: bump(frm, elsewhere, resolved), bumped: true, item: message.item};
			}
			return {row: applyLine(frm, row, resolved), bumped: false, item: message.item};
		} catch (error) {
			if (created) discardRow(frm, row);
			throw error;
		}
	}

	function installFastScan() {
		const proto = window.erpnext?.utils?.BarcodeScanner?.prototype;
		if (!proto || proto.__retail_fast_scan) return;
		proto.__retail_fast_scan = true;
		const original = proto.process_scan;
		proto.process_scan = function () {
			const frm = this.frm;
			const dialogOpen = frm.__quick_receipt?.dialog?.$wrapper?.is?.(":visible");
			if (!lineEligible(frm) || dialogOpen) return original.call(this);
			// set_value("") retriggers this handler. Ignore that re-entry so the
			// native scanner does not price the same barcode a second time.
			if (this.__retail_scan_lock) return Promise.resolve();
			const input = String(this.scan_barcode_field?.value || "").trim();
			if (!input) return original.call(this);
			this.__retail_scan_lock = true;
			frm.__retail_scan_token = (frm.__retail_scan_token || 0) + 1;
			const token = frm.__retail_scan_token;
			frm.__retail_purchase_scan_active = true;
			this.scan_barcode_field.set_value("");
			const scanner = this;
			const restoreScan = () => frm.fields_dict?.scan_barcode?.set_focus?.();
			return fill(frm, {search_value: input, barcode: input}).then(result => {
				if (result?.warehouse) {
					scanner.handle_warehouse_scan({warehouse: result.warehouse});
					scanner.play_success_sound();
					return;
				}
				if (!result?.row) {
					scanner.show_alert(__("Cannot find Item with this Barcode"), "red");
					scanner.play_fail_sound();
					return;
				}
				scanner.show_scan_message(result.row.idx, Boolean(result.bumped), 1);
				scanner.play_success_sound();
			}).catch(error => {
				scanner.play_fail_sound();
				throw error;
			}).finally(() => {
				scanner.__retail_scan_lock = false;
				restoreScan();
				// items_add focuses the new row after 160ms. Put the cursor back
				// on the barcode once that timer has run, unless a newer scan started.
				setTimeout(() => {
					if (frm.__retail_scan_token !== token) return;
					restoreScan();
					frm.__retail_purchase_scan_active = false;
				}, 500);
			});
		};
	}

	window.retail.purchaseLine = {fill, bump, cachedRow, lineMatch};

	if (!document.getElementById("retail-packing-search-style")) {
		$("<style id='retail-packing-search-style'>").text(`
			.awesomplete > ul.retail-packing-results { width: min(560px, 90vw); min-width: min(560px, 90vw); max-width: 90vw; max-height: 360px; overflow: auto; }
			body .awesomplete > ul.retail-packing-results > li:hover { background: #c6ddf6 !important; color: #102a43 !important; }
			.retail-packing-cells { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1.5fr) minmax(0, 1.2fr) minmax(0, .7fr) minmax(0, .6fr); gap: 6px; padding: 4px; }
			.retail-packing-cells > span { min-width: 0; white-space: normal; overflow-wrap: anywhere; }
			.retail-packing-heading { background: var(--fg-color); color: var(--text-color); font-weight: 600; border-bottom: 1px solid var(--border-color); }
		`).appendTo(document.head);
	}

	installFastScan();

	for (const doctype of ["Purchase Receipt", "Purchase Invoice"]) frappe.ui.form.on(doctype, {
		scan_barcode(frm) {
			installScanner(frm);
			installFastScan();
		},
		refresh(frm) {
			installScanner(frm);
			installFastScan();
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
					if (lineEligible(frm)) {
						const result = await window.retail.purchaseLine.fill(frm, {
							item_code: choice.item_code,
							uom: choice.uom,
							barcode: choice.barcode,
						}, row);
						if (!result?.row) frappe.throw(__("Could not load the selected Item."));
						return;
					}
					// Internal transfers keep the native item and UOM handlers.
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

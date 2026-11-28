(function () {
	if (window.__retail_transaction_items_booted) return;
	window.__retail_transaction_items_booted = true;

	function boot() {
		if (typeof window.frappe?.ui?.form?.on !== "function") {
			setTimeout(boot, 100);
			return;
		}
		registerTransactionItems();
	}

	function registerTransactionItems() {
		if (window.__retail_transaction_items_registered) return;
		window.__retail_transaction_items_registered = true;

	const vatItemDoctypes = [
		"Purchase Order Item",
		"Purchase Receipt Item",
		"Purchase Invoice Item",
		"Supplier Quotation Item",
		"Material Request Item",
		"Subcontracting Order Item",
		"Subcontracting Receipt Item",
		"Sales Order Item",
		"Delivery Note Item",
		"Sales Invoice Item",
		"POS Invoice Item",
		"Quotation Item",
		"Opportunity Item",
		"Blanket Order Item",
	];

	const totalsFormDoctypes = {};

	const liveVatFormDoctypes = {
		"Purchase Order": "Purchase Tax",
		"Purchase Receipt": "Purchase Tax",
		"Purchase Invoice": "Purchase Tax",
		"Sales Invoice": "Sales Tax",
		"Sales Order": "Sales Tax",
		"Delivery Note": "Sales Tax",
		"POS Invoice": "Sales Tax",
		"Quotation": "Sales Tax",
	};

	const totalsItemDoctypes = [
		"Purchase Order Item",
		"Purchase Receipt Item",
		"Purchase Invoice Item",
		"Sales Order Item",
	];

	vatItemDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			item_code(frm, cdt, cdn) {
				const row = locals[cdt]?.[cdn];
				forgetVatRate(frm, row);
				if (row) row.__retail_vat_force_sync = true;
				const pending = syncVatRates(frm, cdt, cdn, "rate");
				if (row) delete row.__retail_vat_force_sync;
				scheduleVatSync(frm, cdt, cdn, "rate");
				scheduleVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
				return pending;
			},
			rate(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			price_list_rate(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			net_amount(frm) {
				refreshRowVatAmounts(frm);
			},
			net_rate(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			item_tax_template(frm, cdt, cdn) {
				return refreshVatFromTemplate(frm, cdt, cdn);
			},
			tax_rate(frm, cdt, cdn) {
				return refreshVatFromTemplate(frm, cdt, cdn);
			},
			qty(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "qty");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			uom(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
			},
			conversion_factor(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
			},
			custom_rate_including_vat(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "inclusive");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			amount(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "exclusive_amount");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			custom_amount_including_vat(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "inclusive_amount");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			items_remove(frm) {
				queueVatTaxRowsSync(frm);
			},
		});
	});

	vatItemDoctypes.forEach((child) => {
		frappe.ui.form.on(child.replace(/ Item$/, ""), {
			refresh: refreshRowVatAmounts,
			total_taxes_and_charges: refreshRowVatAmounts,
		});
	});

	function isCompletedPos(frm) {
		return frm?.doc?.doctype === "POS Invoice" && !!frm.doc.custom_pos_completed_payload;
	}

	function refreshRowVatAmounts(frm) {
		if (isCompletedPos(frm)) return;
		// Totals emit one event per row. Coalesce display work for the invoice;
		// never rebuild the whole grid just to repeat a read-only property.
		clearTimeout(frm.__retail_vat_display_timer);
		frm.__retail_vat_display_timer = setTimeout(() => {
			if (frm.__retail_vat_display_running) {
				refreshRowVatAmounts(frm);
				return;
			}
			frm.__retail_vat_display_running = true;
			refreshVatAmounts(frm).finally(() => { frm.__retail_vat_display_running = false; });
		}, 80);
	}

	async function refreshVatAmounts(frm) {
		const grid = frm.fields_dict.items?.grid;
		if (grid?.docfields?.find(df => df.fieldname === "custom_vat_amount")?.read_only !== 1) {
			grid?.update_docfield_property?.("custom_vat_amount", "read_only", 1);
		}
		await Promise.all((frm.doc.items || []).map(async row => {
			const field = frappe.meta.get_docfield(row.doctype, "custom_vat_amount", row.name);
			if (!field) return;
			field.read_only = 1;
			const code = row.item_code;
			const rate = code ? await getVatRate(frm, row, row.doctype) : 0;
			if (row.item_code !== code || !(frm.doc.items || []).includes(row)) return;
			const amount = flt(row.qty) * flt(row.rate);
			const value = flt(amount * rate / 100, cint(field.precision) || 2);
			if (row.custom_vat_amount === value) return;
			row.custom_vat_amount = value;
			grid?.grid_rows_by_docname?.[row.name]?.refresh_field?.("custom_vat_amount");
		}));
	}

	Object.keys(liveVatFormDoctypes).forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				placeVatFieldBeforeGrandTotal(frm);
				if (frm.doc.doctype === "Sales Invoice" && isEditableDraft(frm) && frm.doc.items?.length) {
					return syncVatTaxRows(frm);
				}
			},
			company(frm) {
				delete frm.__retail_vat_rate_memo;
				delete frm.__retail_vat_template_rates;
				queueVatTaxRowsSync(frm);
			},
			cost_center(frm) {
				queueVatTaxRowsSync(frm);
			},
			taxes_and_charges(frm) {
				queueVatTaxRowsSync(frm);
			},
			apply_discount_on(frm) {
				runErpnextTotals(frm);
				placeVatFieldBeforeGrandTotal(frm);
			},
			additional_discount_percentage(frm) {
				runErpnextTotals(frm);
				placeVatFieldBeforeGrandTotal(frm);
			},
			discount_amount(frm) {
				runErpnextTotals(frm);
				placeVatFieldBeforeGrandTotal(frm);
			},
			total_taxes_and_charges(frm) {
				placeVatFieldBeforeGrandTotal(frm);
			},
			grand_total(frm) {
				placeVatFieldBeforeGrandTotal(frm);
			},
		});
	});

	Object.keys(totalsFormDoctypes).forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				renderTransactionTotals(frm);
			},
			net_total(frm) {
				renderTransactionTotals(frm);
			},
			total_taxes_and_charges(frm) {
				renderTransactionTotals(frm);
			},
			grand_total(frm) {
				renderTransactionTotals(frm);
			},
			rounded_total(frm) {
				renderTransactionTotals(frm);
			},
			taxes_and_charges(frm) {
				renderTransactionTotals(frm);
			},
		});
	});

	totalsItemDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			net_amount(frm) {
				renderTransactionTotals(frm);
			},
			item_tax_template(frm) {
				renderTransactionTotals(frm);
			},
			items_remove(frm) {
				renderTransactionTotals(frm);
			},
		});
	});

	frappe.ui.form.on("Sales Taxes and Charges", taxHandlers());
	frappe.ui.form.on("Purchase Taxes and Charges", taxHandlers());

	function scheduleVatTaxRowsSync(frm) {
		if (["Purchase Order", "Purchase Receipt", "Purchase Invoice", "Sales Invoice"].includes(frm.doc.doctype)) {
			queueVatTaxRowsSync(frm);
			return;
		}
		[250, 700].forEach((delay) => {
			setTimeout(() => queueVatTaxRowsSync(frm), delay);
		});
	}

	function vatInputKey(row) {
		return [row.item_code, row.uom, row.qty, row.rate, row.amount, row.price_list_rate, row.net_rate,
			row.conversion_factor, row.item_tax_template, row.tax_rate].join("\u0001");
	}

	function vatRateMemo(frm) {
		return frm.__retail_vat_rate_memo || (frm.__retail_vat_rate_memo = new Map());
	}

	function vatTemplateRates(frm) {
		return frm.__retail_vat_template_rates || (frm.__retail_vat_template_rates = new Map());
	}

	function vatTemplateKey(frm, row) {
		const doc = frm.doc || {};
		return [row.item_tax_template || "", doc.doctype || "", doc.company || "",
			doc.custom_trading_vat_disabled || 0, doc.is_pos || 0].join("\u0001");
	}

	function vatRateMemoKey(frm, row) {
		const doc = frm.doc || {};
		return [row.item_code, row.doctype, doc.doctype, doc.transaction_type || "", row.item_tax_template || "",
			doc.company || "", doc.is_pos || 0, doc.custom_trading_vat_disabled || 0, doc.return_against || ""].join("\u0001");
	}

	function forgetVatRate(frm, row) {
		if (!frm?.__retail_vat_rate_memo || !row?.item_code) return;
		frm.__retail_vat_rate_memo.delete(vatRateMemoKey(frm, row));
	}

	function refreshVatFromTemplate(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		forgetVatRate(frm, row);
		if (row) row.__retail_vat_force_sync = true;
		const pending = syncVatRates(frm, cdt, cdn, "rate");
		if (row) delete row.__retail_vat_force_sync;
		queueVatTaxRowsSync(frm);
		renderTransactionTotals(frm);
		return pending;
	}

	function scheduleVatSync(frm, cdt, cdn, source) {
		[150, 500].forEach((delay) => {
			setTimeout(() => {
				const row = locals[cdt]?.[cdn];
				if (!row || row.__retail_vat_synced_key === vatInputKey(row)) return;
				syncVatRates(frm, cdt, cdn, source);
			}, delay);
		});
	}

	async function syncVatRates(frm, cdt, cdn, source) {
		if (isCompletedPos(frm)) return;
		// Totals write a rate on every line. Following each write with its own
		// VAT request keeps Save waiting until that queue drains.
		if (frm?.__retail_running_erpnext_totals) return;
		if (!isEditableDraft(frm)) return;

		const row = locals[cdt]?.[cdn];
		if (!row || !row.item_code) return;
		const automatic = source === "rate" || source === "qty";
		if (row.__retail_vat_syncing) {
			// Scanning first loads stock-UOM details, then the packing UOM/rate.
			// A repeated event with the same price and quantity is not that second refresh.
			if (automatic && vatInputKey(row) !== row.__retail_vat_sync_key) row.__retail_vat_refresh_pending = true;
			return;
		}
		if (automatic && !row.__retail_vat_force_sync && row.__retail_vat_synced_key === vatInputKey(row)) return;
		if (!frappe.meta.get_docfield(cdt, "custom_rate_including_vat", cdn)) return;

		row.__retail_vat_syncing = true;
		row.__retail_vat_sync_key = vatInputKey(row);
		const generation = frm.__retail_price_generation || 0;
		try {
			const vatRate = await getVatRate(frm, row, cdt);
			// Save moved on. A late VAT reply must not put a rate back.
			if ((frm.__retail_price_generation || 0) !== generation) return;
			const factor = 1 + (flt(vatRate) / 100);
			const precision = cint(frappe.meta.get_docfield(cdt, "rate", cdn)?.precision) || 2;
			const amountPrecision = cint(frappe.meta.get_docfield(cdt, "amount", cdn)?.precision) || precision;
			const amountField = frappe.meta.get_docfield(cdt, "amount", cdn);
			const qty = flt(row.qty);
			const values = {};
			let inclusiveRate = flt(row.custom_rate_including_vat);
			let exclusiveRate = getExclusiveRateForVat(row, qty);

			if (source === "inclusive") {
				exclusiveRate = factor ? inclusiveRate / factor : inclusiveRate;
				values.rate = flt(exclusiveRate, precision);
				if (amountField) {
					values.amount = flt(qty * exclusiveRate, amountPrecision);
				}
			} else if (source === "inclusive_amount") {
				const inclusiveAmount = flt(row.custom_amount_including_vat);
				inclusiveRate = qty ? inclusiveAmount / qty : 0;
				exclusiveRate = factor ? inclusiveRate / factor : inclusiveRate;
				values.custom_rate_including_vat = flt(inclusiveRate, precision);
				values.rate = flt(exclusiveRate, precision);
				if (amountField) {
					values.amount = flt(qty * exclusiveRate, amountPrecision);
				}
			} else if (source === "exclusive_amount") {
				const exclusiveAmount = flt(row.amount);
				exclusiveRate = qty ? exclusiveAmount / qty : 0;
				inclusiveRate = flt(exclusiveRate * factor, precision);
				values.rate = flt(exclusiveRate, precision);
				values.custom_rate_including_vat = inclusiveRate;
				if (row.custom_amount_including_vat !== undefined) {
					values.custom_amount_including_vat = flt(qty * inclusiveRate, amountPrecision);
				}
			} else {
				// Automatic VAT refreshes derive display values from ERPNext's rate.
				// Writing rate here fires its discount handler while item details may
				// still be loading (a transient zero becomes a full-price discount).
				// Only explicit inclusive-rate/amount edits above may change rate.
				inclusiveRate = flt(exclusiveRate * factor, precision);
				values.custom_rate_including_vat = inclusiveRate;
				// Amount is stored directly. set_value would run the amount handler
				// and calculate every line again.
				if (amountField) assignRowAmount(frm, cdt, cdn, row, flt(qty * exclusiveRate, amountPrecision));
			}

			if (source !== "inclusive_amount" && row.custom_amount_including_vat !== undefined) {
				values.custom_amount_including_vat = flt(qty * inclusiveRate, amountPrecision);
			}

			if (frappe.meta.get_docfield(cdt, "custom_vat_amount", cdn)) {
				values.custom_vat_amount = flt(qty * exclusiveRate * flt(vatRate) / 100, amountPrecision);
			}
			if (!Object.keys(values).length) return;
			await setRowValues(frm, cdt, cdn, values);
			if ((frm.__retail_price_generation || 0) !== generation) return;
			if (row) row.__retail_vat_synced_key = vatInputKey(row);
			queueVatTaxRowsSync(frm);
			renderTransactionTotals(frm);
		} finally {
			if (row) {
				row.__retail_vat_syncing = false;
				const pending = row.__retail_vat_refresh_pending && (frm.__retail_price_generation || 0) === generation;
				delete row.__retail_vat_refresh_pending;
				if (pending) {
					row.__retail_vat_force_sync = true;
					try {
						await syncVatRates(frm, cdt, cdn, "rate");
					} finally {
						delete row.__retail_vat_force_sync;
					}
				}
			}
		}
	}


	// Quick Entry waits for the same VAT/totals pipeline before displaying final totals or saving.
	window.retail = window.retail || {};
	window.retail.transaction_items = window.retail.transaction_items || {};
	window.retail.transaction_items.refreshVatDisplays = async frm => {
		const rows = (frm.doc.items || []).filter(row => row.item_code && !row.__retail_vat_syncing);
		const rates = await Promise.all(rows.map(row => getVatRate(frm, row, row.doctype)));
		for (const [index, row] of rows.entries()) {
			if (!(frm.doc.items || []).includes(row)) continue;
			const vat = flt(rates[index]);
			const rate = flt(row.rate);
			const precision = cint(frappe.meta.get_docfield(row.doctype, "rate", row.name)?.precision) || 2;
			const amountPrecision = cint(frappe.meta.get_docfield(row.doctype, "amount", row.name)?.precision) || precision;
			const inclusive = flt(rate * (1 + vat / 100), precision);
			const values = {custom_rate_including_vat: inclusive,
				custom_amount_including_vat: flt(flt(row.qty) * inclusive, amountPrecision),
				custom_vat_amount: flt(flt(row.qty) * rate * vat / 100, amountPrecision)};
			for (const [field, value] of Object.entries(values)) {
				if (!frappe.meta.has_field(row.doctype, field)) continue;
				row[field] = value;
				frm.fields_dict.items?.grid?.grid_rows_by_docname?.[row.name]?.refresh_field?.(field);
			}
		}
	};
	// Save must not sit behind display refreshes. Drop the ones that have not started.
	window.retail.transaction_items.releaseSaveWait = frm => {
		if (!frm) return;
		frm.__retail_price_generation = (frm.__retail_price_generation || 0) + 1;
		frm.__retail_vat_tax_rows_generation = (frm.__retail_vat_tax_rows_generation || 0) + 1;
		clearTimeout(frm.__retail_vat_tax_rows_timer);
		clearTimeout(frm.__retail_whole_bill_timer);
		clearTimeout(frm.__retail_promo_display_timer);
		clearTimeout(frm.__retail_vat_display_timer);
	};
	const purchaseForms = ["Purchase Receipt", "Purchase Invoice"];
	const purchaseReadKey = request => JSON.stringify([request.method,
		Object.keys(request.args || {}).sort().filter(key => request.args[key] != null)
			.map(key => [key, request.args[key]])]);
	// Keep read results for one native field-handler chain, including nested
	// rate/UOM handlers. Release them when that chain finishes, never by TTL.
	const heavyItemForms = ["Purchase Order", "Sales Invoice", "Purchase Receipt", "Purchase Invoice"];
	const calculatedItemFields = ["qty", "stock_qty", "rate", "amount", "price_list_rate", "net_rate", "net_amount",
		"discount_percentage", "discount_amount", "margin_type", "margin_rate_or_amount", "item_tax_rate",
		"custom_rate_including_vat", "custom_amount_including_vat", "custom_vat_amount", "custom_total_stock_qty"];

	function installLightTotals(frm) {
		if (!heavyItemForms.includes(frm?.doc?.doctype)) return;
		const cscript = frm.cscript;
		if (!cscript || cscript.__retail_light_totals || typeof cscript.calculate_taxes_and_totals !== "function") return;
		cscript.__retail_light_totals = true;
		const original = cscript.calculate_taxes_and_totals;
		// Totals already rewrite every row in memory. Rebuilding the whole item
		// grid after each added line is what freezes the form once it has many rows.
		cscript.calculate_taxes_and_totals = function (...args) {
			const nested = frm.__retail_light_depth || 0;
			frm.__retail_light_depth = nested + 1;
			if (!nested) holdItemGrid(frm);
			let result;
			try {
				result = original.apply(this, args);
			} catch (error) {
				releaseItemGrid(frm);
				throw error;
			}
			if (result?.finally) return result.finally(() => releaseItemGrid(frm));
			releaseItemGrid(frm);
			return result;
		};
	}

	function holdItemGrid(frm) {
		frm.__retail_item_names = (frm.doc.items || []).map(row => row.name).join("\u0001");
		frm.__retail_item_refresh_pending = false;
		snapshotItemFigures(frm);
		const field = frm.fields_dict?.items;
		if (field?.refresh) {
			frm.__retail_saved_item_refresh = field.refresh;
			// layout.refresh() still updates totals, taxes, and dependencies.
			// The items control is the piece that rebuilds every row.
			field.refresh = function () { frm.__retail_item_refresh_pending = true; };
		}
		const grid = field?.grid;
		frm.__retail_saved_row_dependency = [];
		for (const gridRow of grid?.grid_rows || []) {
			if (typeof gridRow?.refresh_dependency !== "function" || gridRow.refresh_dependency.__retail_held) continue;
			const original = gridRow.refresh_dependency;
			const held = function () {};
			held.__retail_held = true;
			gridRow.refresh_dependency = held;
			frm.__retail_saved_row_dependency.push([gridRow, original]);
		}
		frm.__retail_saved_refresh_field = frm.refresh_field;
		frm.refresh_field = function (fieldname, ...args) {
			if (fieldname === "items") {
				frm.__retail_item_refresh_pending = true;
				return;
			}
			if (Array.isArray(fieldname)) {
				if (fieldname.includes("items")) frm.__retail_item_refresh_pending = true;
				const rest = fieldname.filter(name => name !== "items");
				if (!rest.length) return;
				return frm.__retail_saved_refresh_field?.call(frm, rest, ...args);
			}
			return frm.__retail_saved_refresh_field?.call(frm, fieldname, ...args);
		};
	}

	function releaseItemGrid(frm) {
		frm.__retail_light_depth = Math.max(0, (frm.__retail_light_depth || 1) - 1);
		if (frm.__retail_light_depth > 0) return;
		const field = frm.fields_dict?.items;
		if (field && frm.__retail_saved_item_refresh) field.refresh = frm.__retail_saved_item_refresh;
		for (const [gridRow, original] of frm.__retail_saved_row_dependency || []) {
			if (gridRow.refresh_dependency?.__retail_held) gridRow.refresh_dependency = original;
		}
		if (frm.__retail_saved_refresh_field) frm.refresh_field = frm.__retail_saved_refresh_field;
		delete frm.__retail_saved_item_refresh;
		delete frm.__retail_saved_row_dependency;
		delete frm.__retail_saved_refresh_field;
		const refreshPending = frm.__retail_item_refresh_pending;
		delete frm.__retail_item_refresh_pending;
		const names = (frm.doc.items || []).map(row => row.name).join("\u0001");
		const grid = frm.fields_dict?.items?.grid;
		const missing = !grid || (frm.doc.items || []).some(row => row?.name && !grid.grid_rows_by_docname?.[row.name]);
		if (refreshPending || names !== frm.__retail_item_names || missing) {
			frm.refresh_field?.("items");
			return;
		}
		paintItemFigures(frm);
	}

	function snapshotItemFigures(frm) {
		const grid = frm.fields_dict?.items?.grid;
		if (!grid?.grid_rows_by_docname) return;
		for (const row of frm.doc.items || []) {
			const gridRow = grid.grid_rows_by_docname[row.name];
			if (!gridRow) continue;
			const seen = gridRow.__retail_figures || (gridRow.__retail_figures = {});
			for (const field of calculatedItemFields) {
				if (Object.prototype.hasOwnProperty.call(row, field)) seen[field] = row[field];
			}
		}
	}

	function paintItemFigures(frm) {
		const grid = frm.fields_dict?.items?.grid;
		if (!grid?.grid_rows_by_docname) return;
		for (const row of frm.doc.items || []) {
			const gridRow = grid.grid_rows_by_docname[row.name];
			if (!gridRow?.refresh_field) continue;
			const seen = gridRow.__retail_figures || (gridRow.__retail_figures = {});
			for (const field of calculatedItemFields) {
				if (!Object.prototype.hasOwnProperty.call(row, field) || seen[field] === row[field]) continue;
				seen[field] = row[field];
				gridRow.refresh_field(field);
			}
		}
	}

	const qtyKeepRateForms = ["Purchase Order", "Purchase Receipt", "Purchase Invoice",
		"Sales Invoice", "Sales Order", "Delivery Note", "Quotation"];
	function installQtyKeepRate(frm) {
		if (!qtyKeepRateForms.includes(frm?.doc?.doctype)) return;
		const cscript = frm.cscript;
		if (!cscript || cscript.__retail_qty_keep_rate || typeof cscript.qty !== "function") return;
		cscript.__retail_qty_keep_rate = true;
		// Quantity changes the amount. It must not ask the price list to replace the
		// unit rate; that response arrives a moment later and puts the old price back.
		cscript.qty = function (doc, cdt, cdn) {
			frm.__retail_price_generation = (frm.__retail_price_generation || 0) + 1;
			const row = locals[cdt]?.[cdn];
			if (!row?.item_code) return;
			if ((doc?.doctype === "Purchase Receipt" || (doc?.doctype === "Purchase Invoice" && doc.update_stock))
				&& typeof this.calculate_received_qty === "function") {
				this.calculate_received_qty(doc, cdt, cdn);
			}
			this.conversion_factor?.(doc, cdt, cdn, true);
			return this.calculate_taxes_and_totals?.();
		};
		if (typeof frm.call === "function" && !frm.__retail_price_generation_guard) {
			frm.__retail_price_generation_guard = true;
			const call = frm.call;
			frm.call = function (opts, ...args) {
				const method = typeof opts === "object" ? String(opts?.method || "") : "";
				if (opts?.callback && (method.includes("apply_pricing_rule") || method.includes("apply_price_list"))) {
					const token = frm.__retail_price_generation || 0;
					const original = opts.callback;
					opts.callback = function (...cbArgs) {
						if ((frm.__retail_price_generation || 0) !== token) return;
						return original.apply(this, cbArgs);
					};
				}
				return call.call(this, opts, ...args);
			};
		}
	}

	function installColumnDisplayBatch(frm, grid) {
		const controller = frm.cscript;
		if (!controller?.toggle_item_grid_columns || controller.__retail_column_display_batch) return;
		controller.__retail_column_display_batch = true;
		const toggle = controller.toggle_item_grid_columns;
		controller.toggle_item_grid_columns = function (...args) {
			// Native currency/discount labels toggle eight columns in sequence.
			// Keep every metadata and cell update, but paint the completed layout once.
			const refresh = grid.refresh;
			let requested = false;
			grid.refresh = function () { requested = true; };
			try { return toggle.apply(this, args); }
			finally {
				grid.refresh = refresh;
				if (requested) refresh.call(grid);
			}
		};
	}

	function installPurchaseGridRefresh(frm) {
		installQtyKeepRate(frm);
		// Same paged refresh as Purchase Invoice. Purchase Order and Sales Invoice
		// paginate at 50 rows too, and the empty off-page slots must be skipped.
		if (!["Purchase Order", "Purchase Receipt", "Purchase Invoice", "Sales Invoice"].includes(frm?.doc?.doctype)) return;
		const grid = frm.fields_dict?.items?.grid;
		if (grid) installColumnDisplayBatch(frm, grid);
		if (!grid?.refresh || grid.__retail_incremental_refresh) return;
		grid.__retail_incremental_refresh = true;
		const refresh = grid.refresh;
		let painted = null;
		let deferredDialog;
		const fields = () => [...new Set(["idx", "__checked", ...(grid.docfields || []).map(df => df.fieldname).filter(Boolean)])];
		const safeJson = (value) => {
			try { return JSON.stringify(value); }
			catch { return null; }
		};
		const values = (row, keys) => Object.fromEntries(keys.map(key => [key, safeJson(row?.[key])]));
		const layout = () => safeJson([
			frm.doc.name, frm.doc.docstatus, grid.grid_pagination?.page_index,
			grid.grid_pagination?.page_length,
			grid.df?.read_only, grid.df?.hidden, grid.df?.reqd,
			(grid.docfields || []).map(df => [df.fieldname, df.fieldtype, df.label, df.options,
				Number(df.hidden || 0), Number(df.read_only || 0), Number(df.reqd || 0),
				df.depends_on, df.read_only_depends_on, df.mandatory_depends_on, df.columns, df.width_px]),
			(grid.visible_columns || []).flatMap(entry => entry?.[0]?.fieldname ? [[entry[0].fieldname, entry[1], entry[0].width_px]] : []),
		]);
		const structure = () => safeJson([layout(), (frm.doc.items || []).map(row => [row?.name, row?.idx, Boolean(row?.__checked)])]);
		function snapshot() {
			const keys = fields();
			painted = {layout: layout(), structure: structure(), rows: new Map((grid.grid_rows || [])
				.filter(row => row.doc?.name).map(row => [row.doc.name, values(row.doc, keys)]))};
		}
		grid.refresh = function (...args) {
			// A redraw error rejects the item-details promise and shows "Could not load Item".
			try {
			return refreshGrid.apply(this, args);
			} catch (error) {
				globalThis.console?.error?.(error);
			}
		};
		function refreshGrid(...args) {
			// Quick Entry edits the same model. Paint its dialog now and the hidden
			// Desk grid once on close, rather than rebuilding both for each item.
			const dialog = frm.__quick_receipt?.dialog;
			if (Number(frm.doc.docstatus || 0) === 0 && dialog?.$wrapper?.is?.(":visible")) {
				if (deferredDialog !== dialog) {
					deferredDialog = dialog;
					dialog.$wrapper.one("hidden.bs.modal.retailItemGrid", () => {
						deferredDialog = null;
						frm.refresh_field("items");
					});
				}
				return;
			}
			const rows = frm.doc.items || [];
			const length = Number(grid.grid_pagination?.page_length) || rows.length;
			const start = (Number(grid.grid_pagination?.page_index || 1) - 1) * length;
			const missing = rows.slice(start, start + length).some(row => !grid.grid_rows_by_docname?.[row.name]);
			const byName = new Map(rows.map(row => [row.name, row]));
			const replaced = (grid.grid_rows || []).some(row => row.doc?.name && byName.has(row.doc.name) && byName.get(row.doc.name) !== row.doc);
			if (!painted || args.length || Number(frm.doc.docstatus || 0) !== 0 || missing ||
				replaced || Object.keys(grid.filter || {}).length || painted.structure !== structure()) {
				const held = [];
				// Let native Grid add/remove/reindex rows, retaining controls in the
				// existing rows when neither their values nor their layout changed.
				if (painted && !args.length && !replaced && Number(frm.doc.docstatus || 0) === 0 &&
					!Object.keys(grid.filter || {}).length && painted.layout === layout()) {
					const keys = fields();
					// Pagination deletes off-page slots. for...of yields those holes
					// and a missing row aborts refresh, so Save never reaches the server.
					for (const row of (grid.grid_rows || []).filter(row => row?.doc)) {
						if (!row.doc?.name || !byName.has(row.doc.name) || typeof row.refresh !== "function") continue;
						if (JSON.stringify(painted.rows.get(row.doc.name)) !== JSON.stringify(values(row.doc, keys))) continue;
						held.push([row, row.refresh]);
						row.refresh = function () {};
					}
				}
				try {
					const result = refresh.apply(this, args);
					snapshot();
					return result;
				} finally {
					for (const [row, original] of held) row.refresh = original;
				}
			}
			const keys = fields();
			let changed = false;
			for (const gridRow of (grid.grid_rows || []).filter(row => row?.doc)) {
				const row = gridRow.doc;
				if (!row?.name) continue;
				const previous = painted.rows.get(row.name) || {};
				const current = values(row, keys);
				const dirty = keys.filter(key => previous[key] !== current[key]);
				if (!dirty.length) continue;
				if (row.item_code && row.item_name) window.frappe?.utils?.add_link_title?.("Item", row.item_code, row.item_name);
				// Preserve native field rendering, dependencies and Link controls.
				// Refreshing only committed changed values also preserves draft text
				// and caret positions in unrelated active inputs.
				for (const key of dirty) {
					if (!gridRow.columns || gridRow.columns[key] || gridRow.grid_form?.fields_dict?.[key]) {
						try { gridRow.refresh_field(key); }
						catch (error) { globalThis.console?.error?.(error); }
					}
				}
				if (dirty.includes("item_code") && !dirty.includes("item_name")) {
					try { gridRow.refresh_field("item_name"); }
					catch (error) { globalThis.console?.error?.(error); }
				}
				gridRow.refresh_dependency?.();
				painted.rows.set(row.name, values(row, keys));
				changed = true;
			}
			if (changed) window.retail?.scrollable_grid?.scheduleLayout?.(grid);
		}
		// Grid creates this bound callback before Retail installs its wrapper.
		// Rebind it too: metadata updates otherwise bypass the incremental path.
		if (window.frappe?.utils?.debounce) grid.debounced_refresh = window.frappe.utils.debounce(grid.refresh.bind(grid), 100);
		// Capture what is already on screen before item handlers change the model.
		if (grid.grid_rows?.length) snapshot();
	}

	function installPurchaseActionReads(frm) {
		installPurchaseGridRefresh(frm);
		installLightTotals(frm);
		const manager = frm.script_manager;
		if (!manager || manager.__retail_purchase_actions) return;
		manager.__retail_purchase_actions = true;
		const trigger = manager.trigger;
		manager.trigger = function (event, cdt, cdn, ...args) {
			if (Number(frm.doc.docstatus || 0) !== 0 || frm.__quick_receipt?.dialog?.$wrapper.is(":visible") ||
				cdt !== frm.doc.doctype + " Item" || !locals[cdt]?.[cdn]?.item_code ||
				!["item_code", "uom", "qty", "rate", "price_list_rate", "conversion_factor",
					"item_tax_template", "tax_rate", "net_rate", "amount",
					"custom_rate_including_vat", "custom_amount_including_vat"].includes(event)) {
				return trigger.call(this, event, cdt, cdn, ...args);
			}
			const action = frm.__retail_purchase_action ||= {reads: new Map(), bundles: new Map(), items: new Map(), active: 0};
			action.active++;
			if (event === "item_code") {
				const row = locals[cdt][cdn];
				const args = {item_code: row.item_code, parent_doctype: frm.doc.doctype,
					uom: row.uom, transaction_type: frm.doc.transaction_type, item_tax_template: row.item_tax_template};
				if (frm.doc.doctype === "Sales Invoice") Object.assign(args, {
					company: frm.doc.company, is_pos: frm.doc.is_pos || 0,
					is_consolidated: frm.doc.is_consolidated || 0, return_against: frm.doc.return_against,
					docstatus: frm.doc.docstatus || 0, custom_trading_vat_disabled: frm.doc.custom_trading_vat_disabled || 0,
				});
				const key = purchaseReadKey({args});
				if (!action.bundles.has(key)) {
					// Use the existing permission-checked Quick Entry read bundle.
					// Native handlers still own every field write and calculation.
					action.bundles.set(key, Promise.resolve().then(() => frappe.call({
						method: "retail.domains.purchase.quick_entry.item_data", args,
					})).then(result => {
						const item = result.message?.item;
						if (item?.name === row.item_code) action.items.set(item.name, item);
						return result.message?.lookups || [];
					}, () => []));
				}
			}
			let result;
			try {
				result = trigger.call(this, event, cdt, cdn, ...args);
			} catch (error) {
				finish();
				throw error;
			}
			return Promise.resolve(result).finally(finish);
			function finish() {
				if (--action.active === 0 && frm.__retail_purchase_action === action) {
					delete frm.__retail_purchase_action;
				}
			}
		};
	}
	[...purchaseForms, "Sales Invoice"].forEach(doctype => frappe.ui.form.on(doctype, {refresh: installPurchaseActionReads}));
	frappe.ui.form.on("Purchase Order", {refresh: installPurchaseGridRefresh});
	for (const doctype of ["Sales Order", "Delivery Note", "Quotation"]) {
		frappe.ui.form.on(doctype, {refresh: installQtyKeepRate});
	}
	window.retail.transaction_items.preparedPurchaseItem = async (frm, itemCode) => {
		const action = frm.__retail_purchase_action;
		if (!action) return null;
		await Promise.all(action.bundles.values());
		return action.items.get(itemCode) || null;
	};
	// Share identical reads only while they are in flight. The next edit always
	// reads fresh data; rejected requests must also be retried normally.
	window.retail.transaction_items.purchaseRead = function (frm, request) {
		if (!["Purchase Order", "Purchase Receipt", "Purchase Invoice", "Sales Invoice"].includes(frm?.doc?.doctype)) return frappe.call(request);
		const action = frm.__retail_purchase_action;
		const pending = action?.reads || (frm.__retail_purchase_reads ||= new Map());
		const key = purchaseReadKey(request);
		if (!pending.has(key)) {
			const read = Promise.all([...(action?.bundles?.values() || [])]).then(bundles => {
				const prepared = bundles.flat().find(result => purchaseReadKey(result) === key);
				return prepared ? {message: prepared.message} : frappe.call(request);
			}).then(value => {
				if (!action) pending.delete(key);
				return value;
			}, error => { pending.delete(key); throw error; });
			pending.set(key, read);
		}
		return pending.get(key);
	};
	window.retail.transaction_items.flushVatTaxRows = async frm => {
		while (frm.__retail_syncing_vat_tax_rows || frm.__retail_running_erpnext_totals) {
			await new Promise(resolve => setTimeout(resolve, 16));
		}
		clearTimeout(frm.__retail_vat_tax_rows_timer);
		frm.__retail_vat_tax_rows_generation = (frm.__retail_vat_tax_rows_generation || 0) + 1;
		await syncVatTaxRows(frm, true);
	};

	function queueVatTaxRowsSync(frm) {
		if (frm?.__retail_running_erpnext_totals) return;
		if (!canSyncVatTaxRows(frm)) return;

		clearTimeout(frm.__retail_vat_tax_rows_timer);
		const generation = frm.__retail_vat_tax_rows_generation = (frm.__retail_vat_tax_rows_generation || 0) + 1;
		frm.__retail_vat_tax_rows_timer = setTimeout(async () => {
			if (["Purchase Order", "Purchase Receipt", "Purchase Invoice", "Sales Invoice"].includes(frm.doc.doctype)) {
				// Item/UOM/qty handlers make several native pricing requests. Wait
				// for those callbacks before sending the entire document for VAT;
				// intermediate VAT calls otherwise extend every after_ajax barrier.
				await frappe.after_ajax();
				if (generation !== frm.__retail_vat_tax_rows_generation) return;
				if (frm.__retail_purchase_action?.active || frm.__quick_receipt?.pending) {
					queueVatTaxRowsSync(frm);
					return;
				}
			}
			await syncVatTaxRows(frm);
		}, 200);
	}

	function canSyncVatTaxRows(frm) {
		return Boolean(
			frm?.doc
			&& liveVatFormDoctypes[frm.doc.doctype]
			&& isEditableDraft(frm)
			&& frm.fields_dict?.taxes
			&& Array.isArray(frm.doc.items)
		);
	}

	function isEditableDraft(frm) {
		return cint(frm?.doc?.docstatus) === 0;
	}

	function vatTaxStructureKey(frm) {
		const doc = frm.doc || {};
		const items = (doc.items || []).map(row => [row.name || "", row.item_code || "", row.item_tax_template || ""].join("\u0001")).join("\u0002");
		return [doc.doctype, doc.company || "", doc.cost_center || "", doc.transaction_type || "",
			doc.custom_trading_vat_disabled ? 1 : 0, items].join("\u0001");
	}

	async function syncVatTaxRows(frm, force) {
		if (isCompletedPos(frm)) return;
		if (!canSyncVatTaxRows(frm) || frm.__retail_syncing_vat_tax_rows) return;
		const key = vatTaxStructureKey(frm);
		if (!force && key === frm.__retail_vat_tax_key) return;

		frm.__retail_syncing_vat_tax_rows = true;
		try {
			const response = await frappe.call({
				method: "retail.domains.transactions.vat.get_transaction_vat_tax_rows",
				args: {
					doc: frm.doc,
				},
			});
			const setup = normalizeVatTaxSetup(response.message);
			if (response.message?.vat_disabled) {
				const converting = !cint(frm.doc.custom_trading_vat_disabled);
				const accounts = response.message.vat_accounts || [];
				frm.doc.taxes = (frm.doc.taxes || []).filter(row => !accounts.includes(row.account_head));
				frm.doc.taxes_and_charges = "";
				for (const row of frm.doc.items || []) {
					const values = response.message.item_values?.[row.name];
					if (converting && values && flt(row.rate) === flt(values.source_rate)) {
						row.rate = values.rate;
						row.price_list_rate = values.price_list_rate;
						row.discount_amount = values.discount_amount;
					}
					row.item_tax_template = "";
					row.item_tax_rate = "{}";
					row.custom_vat_amount = 0;
					row.custom_rate_including_vat = flt(row.rate);
					row.custom_amount_including_vat = flt(row.qty) * flt(row.rate);
				}
				frm.doc.custom_trading_vat_disabled = 1;
			} else if (frm.doc.doctype === "Sales Invoice") {
				frm.doc.custom_trading_vat_disabled = 0;
			}
			applyItemTaxRates(frm, setup.item_tax_rates);
			replaceManagedVatTaxRows(frm, setup.tax_rows);
			await runErpnextTotals(frm);
			placeVatFieldBeforeGrandTotal(frm);
			if (vatTaxStructureKey(frm) === key) frm.__retail_vat_tax_key = key;
		} finally {
			frm.__retail_syncing_vat_tax_rows = false;
		}
	}

	function normalizeVatTaxSetup(message) {
		if (Array.isArray(message)) {
			return { tax_rows: message, item_tax_rates: {} };
		}
		return {
			tax_rows: message?.tax_rows || [],
			item_tax_rates: message?.item_tax_rates || {},
		};
	}

	function applyItemTaxRates(frm, itemTaxRates) {
		Object.entries(itemTaxRates || {}).forEach(([rowName, itemTaxRate]) => {
			const row = (frm.doc.items || []).find((item) => item.name === rowName);
			if (!row || row.item_tax_rate === undefined) return;
			row.item_tax_rate = itemTaxRate || "{}";
			frm.fields_dict.items?.grid?.grid_rows_by_docname?.[row.name]?.refresh_field?.("item_tax_rate");
		});
	}

	function replaceManagedVatTaxRows(frm, taxRows) {
		const taxLabel = liveVatFormDoctypes[frm.doc.doctype];
		const taxTable = frm.doc.taxes || [];
		const managedRows = taxTable.filter((row) => isManagedVatTaxRow(row, taxLabel));
		// Loading a saved draft must not recreate identical tax rows: add_child
		// marks the form dirty and replaces Submit with Save on every fresh visit.
		if (managedRows.length === taxRows.length && taxRows.every((values, index) =>
			Object.entries(values).every(([field, value]) => {
				// Purchase tax rows have category/add_deduct_tax; Sales rows do not.
				if (!frappe.meta.get_docfield(managedRows[index].doctype, field, frm.doc.name)) return true;
				const current = managedRows[index][field];
				return typeof value === "number" ? Number(current || 0) === value :
					(current ?? "") === (value ?? "");
			}))) return;
		managedRows.forEach((row) => frappe.model.clear_doc(row.doctype, row.name));
		frm.doc.taxes = taxTable.filter((row) => !isManagedVatTaxRow(row, taxLabel));

		taxRows.forEach((values) => {
			const row = frm.add_child("taxes");
			Object.assign(row, values);
		});

		refreshTaxTable(frm);
	}

	async function runErpnextTotals(frm) {
		if (isCompletedPos(frm)) return;
		if (!frm?.doc || frm.__retail_running_erpnext_totals) return;

		frm.__retail_running_erpnext_totals = true;
		try {
			if (frm.cscript?.calculate_taxes_and_totals) {
				await frm.cscript.calculate_taxes_and_totals();
			} else {
				frm.refresh_fields();
			}
			placeVatFieldBeforeGrandTotal(frm);
		} finally {
			frm.__retail_running_erpnext_totals = false;
		}
		await window.retail.transaction_items.refreshVatDisplays?.(frm);
	}

	function placeVatFieldBeforeGrandTotal(frm) {
		if (!liveVatFormDoctypes[frm?.doc?.doctype]) return;
		const vatField = frm.fields_dict?.total_taxes_and_charges;
		const grandField = frm.fields_dict?.grand_total;
		if (!vatField || !grandField) return;

		frm.set_df_property("total_taxes_and_charges", "hidden", 0);
		frm.set_df_property("total_taxes_and_charges", "label", __("VAT"));
		vatField.df.hidden = 0;
		vatField.df.label = __("VAT");
		vatField.refresh?.();

		const vatWrapper = $(vatField.wrapper);
		const grandWrapper = $(grandField.wrapper);
		if (!vatWrapper.length || !grandWrapper.length) return;

		vatWrapper.removeClass("hide-control").show();
		vatWrapper.insertBefore(grandWrapper);
	}

	function refreshTaxTable(frm) {
		frm.refresh_field("taxes");
	}

	function isManagedVatTaxRow(row, taxLabel) {
		const description = String(row?.description || "").trim();
		return description.startsWith(`${taxLabel} [`);
	}

	function assignRowAmount(frm, cdt, cdn, row, amount) {
		if (!row || row.amount === amount) return;
		row.amount = amount;
		frm.fields_dict?.items?.grid?.grid_rows_by_docname?.[cdn]?.refresh_field?.("amount");
	}

	async function setRowValues(frm, cdt, cdn, values) {
		const row = locals[cdt]?.[cdn];
		const changed = [];
		for (const [fieldname, value] of Object.entries(values)) {
			if (row && row[fieldname] === value) continue;
			changed.push(fieldname);
			await frappe.model.set_value(cdt, cdn, fieldname, value);
		}
		const gridRow = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[cdn];
		changed.forEach((fieldname) => gridRow?.refresh_field?.(fieldname));
	}

	function getExclusiveRateForVat(row, qty) {
		if (hasEnteredValue(row.rate)) return flt(row.rate);
		if (qty && hasEnteredValue(row.amount) && flt(row.amount)) return flt(row.amount) / qty;
		if (hasEnteredValue(row.net_rate) && flt(row.net_rate)) return flt(row.net_rate);
		if (hasEnteredValue(row.price_list_rate) && flt(row.price_list_rate)) return flt(row.price_list_rate);
		return flt(row.rate);
	}

	function rememberVatRate(frm, row, rate) {
		const known = vatRateMemo(frm);
		known.set(vatRateMemoKey(frm, row), rate);
		if (row?.item_tax_template) vatTemplateRates(frm).set(vatTemplateKey(frm, row), rate);
		return rate;
	}

	function vatRateRequest(frm, row, childDoctype) {
		const parentDoc = frm?.doc || {};
		return {
			method: "retail.domains.transactions.vat.get_transaction_item_vat_rate",
			args: {
				item_code: row.item_code,
				child_doctype: childDoctype,
				parent_doctype: parentDoc.doctype,
				transaction_type: parentDoc.transaction_type,
				item_tax_template: row.item_tax_template,
				company: parentDoc.company, is_pos: parentDoc.is_pos || 0,
				is_consolidated: parentDoc.is_consolidated || 0,
				return_against: parentDoc.return_against, docstatus: parentDoc.docstatus || 0,
				custom_trading_vat_disabled: parentDoc.custom_trading_vat_disabled || 0,
			},
		};
	}

	async function fetchOneVatRate(frm, row, childDoctype) {
		const request = vatRateRequest(frm, row, childDoctype);
		const response = await (frm.__quick_receipt?.lookup(request) || window.retail.transaction_items.purchaseRead(frm, request));
		return rememberVatRate(frm, row, flt(response.message));
	}

	async function flushVatRateBatch(frm) {
		const batch = frm.__retail_vat_rate_batch || [];
		frm.__retail_vat_rate_batch = [];
		if (!batch.length) return;
		if (batch.length === 1) {
			const item = batch[0];
			try {
				item.resolve(await fetchOneVatRate(frm, item.row, item.childDoctype));
			} catch (error) {
				item.reject(error);
			}
			return;
		}
		const parentDoc = frm.doc || {};
		try {
			const response = await frappe.call({
				method: "retail.domains.transactions.vat.get_transaction_item_vat_rates",
				type: "POST",
				args: {
					parent_doctype: parentDoc.doctype,
					company: parentDoc.company,
					transaction_type: parentDoc.transaction_type,
					is_pos: parentDoc.is_pos || 0,
					is_consolidated: parentDoc.is_consolidated || 0,
					return_against: parentDoc.return_against,
					docstatus: parentDoc.docstatus || 0,
					custom_trading_vat_disabled: parentDoc.custom_trading_vat_disabled || 0,
					rows: batch.map(item => ({
						item_code: item.row.item_code,
						child_doctype: item.childDoctype,
						item_tax_template: item.row.item_tax_template || "",
					})),
				},
			});
			const rates = response.message || [];
			batch.forEach((item, index) => item.resolve(rememberVatRate(frm, item.row, flt(rates[index]))));
		} catch (error) {
			batch.forEach(item => item.reject(error));
		}
	}

	function getVatRate(frm, row, childDoctype) {
		const parentDoc = frm?.doc || {};
		const rowRate = flt(row.tax_rate);
		if (rowRate && parentDoc.doctype !== "Sales Invoice") return Promise.resolve(rowRate);

		const known = vatRateMemo(frm);
		const key = vatRateMemoKey(frm, row);
		if (known.has(key)) return Promise.resolve(known.get(key));
		if (row.item_tax_template) {
			const templateKey = vatTemplateKey(frm, row);
			const templates = vatTemplateRates(frm);
			if (templates.has(templateKey)) return Promise.resolve(rememberVatRate(frm, row, templates.get(templateKey)));
		}

		const waiting = frm.__retail_vat_rate_wait || (frm.__retail_vat_rate_wait = new Map());
		if (waiting.has(key)) return waiting.get(key);
		let tracked;
		const promise = new Promise((resolve, reject) => {
			const batch = frm.__retail_vat_rate_batch || (frm.__retail_vat_rate_batch = []);
			batch.push({row, childDoctype, key, resolve, reject});
		});
		tracked = promise.finally(() => {
			if (frm.__retail_vat_rate_wait?.get(key) === tracked) frm.__retail_vat_rate_wait.delete(key);
		});
		waiting.set(key, tracked);
		if (!frm.__retail_vat_rate_flush) {
			frm.__retail_vat_rate_flush = Promise.resolve().then(() => {
				frm.__retail_vat_rate_flush = null;
				return flushVatRateBatch(frm);
			});
		}
		return tracked;
	}

	function taxHandlers() {
		return {
			tax_amount_after_discount_amount(frm) {
				renderTransactionTotals(frm);
			},
			tax_amount(frm) {
				renderTransactionTotals(frm);
			},
			rate(frm) {
				renderTransactionTotals(frm);
			},
			description(frm) {
				renderTransactionTotals(frm);
			},
		};
	}

	function renderTransactionTotals(frm) {
		if (!totalsFormDoctypes[frm.doctype]) return;

		const field = frm.fields_dict.custom_retail_totals_summary;
		if (!field) return;
		applyTotalsLayout(field);

		const currency = frm.doc.currency;
		const subtotal = getSubtotal(frm);
		const tax = getTaxAmount(frm);
		const inclusiveTotal = getInclusiveTotal(frm);
		const total = hasEnteredValue(inclusiveTotal)
			? inclusiveTotal
			: hasEnteredValue(frm.doc.grand_total)
				? flt(frm.doc.grand_total)
				: subtotal + tax;

		field.$wrapper.html(`
			<style>
				.retail-transaction-totals {
					border-top: 1px solid var(--border-color);
					margin-top: 8px;
					max-width: 100%;
				}
				.retail-transaction-totals-section > .section-body {
					align-items: flex-start;
					display: flex;
				}
				.retail-transaction-totals-section > .section-body > .retail-transaction-spacer-column {
					display: none !important;
				}
				.retail-transaction-totals-section > .section-body > .retail-transaction-quantity-column {
					flex: 0 0 32% !important;
					max-width: 32% !important;
				}
				.retail-transaction-totals-section > .section-body > .retail-transaction-totals-column {
					flex: 0 0 50% !important;
					margin-left: auto;
					max-width: 50% !important;
				}
				@media (max-width: 767.98px) {
					.retail-transaction-totals-section > .section-body {
						display: block;
					}
					.retail-transaction-totals-section > .section-body > .retail-transaction-quantity-column,
					.retail-transaction-totals-section > .section-body > .retail-transaction-totals-column {
						flex: 0 0 100% !important;
						max-width: 100% !important;
					}
				}
				.retail-transaction-total-row {
					align-items: center;
					border-bottom: 1px solid var(--border-color);
					display: grid;
					grid-template-columns: minmax(0, 1fr) auto;
					gap: 16px;
					min-height: 42px;
					padding: 8px 4px;
				}
				.retail-transaction-total-row.total {
					background: var(--subtle-fg);
					font-weight: 700;
					padding-left: 8px;
					padding-right: 8px;
				}
				.retail-transaction-total-label {
					color: var(--text-muted);
					overflow-wrap: anywhere;
				}
				.retail-transaction-total-row.total .retail-transaction-total-label,
				.retail-transaction-total-row.total .retail-transaction-total-value {
					color: var(--primary);
				}
				.retail-transaction-total-value {
					font-variant-numeric: tabular-nums;
					text-align: right;
				}
			</style>
			<div class="retail-transaction-totals">
				${getTotalRow(__("Sub Total"), subtotal, currency)}
				${getTotalRow(getTaxLabel(frm), tax, currency)}
				${getTotalRow(__("Total ({0})", [currency || ""]), total, currency, true)}
			</div>
		`);
	}

	function applyTotalsLayout(field) {
		const section = field.$wrapper.closest(".form-section");
		if (!section?.length) return;

		const columns = section.children(".section-body").children(".form-column");
		const totalsColumn = field.$wrapper.closest(".form-column");
		const quantityColumn = columns
			.filter((_, column) => $(column).find('[data-fieldname="total_qty"]').length)
			.first();

		section.addClass("retail-transaction-totals-section");
		columns.removeClass(
			"retail-transaction-quantity-column retail-transaction-totals-column retail-transaction-spacer-column"
		);

		quantityColumn.addClass("retail-transaction-quantity-column");
		totalsColumn.addClass("retail-transaction-totals-column");
		columns.not(quantityColumn).not(totalsColumn).addClass("retail-transaction-spacer-column");
	}

	function getTotalRow(label, value, currency, isTotal) {
		return `
			<div class="retail-transaction-total-row ${isTotal ? "total" : ""}">
				<div class="retail-transaction-total-label">${escapeHtml(label)}</div>
				<div class="retail-transaction-total-value">${format_currency(value, currency)}</div>
			</div>
		`;
	}

	function getSubtotal(frm) {
		const items = frm.doc.items || [];
		const itemSubtotal = items.reduce((total, row) => total + getExclusiveAmount(row), 0);

		if (items.length) return flt(itemSubtotal);
		return flt(itemSubtotal || frm.doc.net_total || frm.doc.total || frm.doc.base_net_total || frm.doc.base_total);
	}

	function getTaxAmount(frm) {
		const items = frm.doc.items || [];
		const hasInclusiveAmount = items.some((row) => hasEnteredValue(getInclusiveAmount(row)));
		const itemTax = items.reduce((total, row) => {
			const inclusiveAmount = getInclusiveAmount(row);
			if (!hasEnteredValue(inclusiveAmount)) return total;
			return total + (inclusiveAmount - getExclusiveAmount(row));
		}, 0);

		if (hasInclusiveAmount) return flt(itemTax);

		const rowTax = (frm.doc.taxes || []).reduce((total, row) => {
			const amount = row.tax_amount_after_discount_amount ?? row.tax_amount;
			return total + flt(amount);
		}, 0);

		if (rowTax) return rowTax;
		return flt(frm.doc.total_taxes_and_charges);
	}

	function getInclusiveTotal(frm) {
		const items = frm.doc.items || [];
		if (!items.some((row) => hasEnteredValue(getInclusiveAmount(row)))) return null;
		return flt(items.reduce((total, row) => total + flt(getInclusiveAmount(row)), 0));
	}

	function getInclusiveAmount(row) {
		const exclusiveAmount = getExclusiveAmount(row);
		const inclusiveRate = flt(row.custom_rate_including_vat);
		if (hasEnteredValue(row.custom_rate_including_vat) && (inclusiveRate || !exclusiveAmount)) {
			return flt(row.qty) * inclusiveRate;
		}
		const inclusiveAmount = flt(row.custom_amount_including_vat);
		if (hasEnteredValue(row.custom_amount_including_vat) && (inclusiveAmount || !exclusiveAmount)) {
			return inclusiveAmount;
		}
		return null;
	}

	function getExclusiveAmount(row) {
		if (hasEnteredValue(row.rate)) return flt(row.qty) * flt(row.rate);
		return flt(row.amount);
	}

	function getTaxLabel(frm) {
		const template = frm.doc.taxes_and_charges;
		if (template) return __("{0} [{1}]", [totalsFormDoctypes[frm.doctype], template]);

		const taxRows = frm.doc.taxes || [];
		const rates = [...new Set(taxRows.map((row) => flt(row.rate)).filter((rate) => rate))];
		if (rates.length === 1) return __("{0} [{1}%]", [totalsFormDoctypes[frm.doctype], rates[0]]);

		const description = taxRows.map((row) => row.description).filter(Boolean)[0];
		if (!description) return __(totalsFormDoctypes[frm.doctype]);
		if (description.startsWith(`${totalsFormDoctypes[frm.doctype]} [`)) return __(description);
		return __("{0} [{1}]", [totalsFormDoctypes[frm.doctype], description]);
	}

	function hasEnteredValue(value) {
		return value !== undefined && value !== null && value !== "";
	}

	function escapeHtml(value) {
		if (frappe.utils?.escape_html) return frappe.utils.escape_html(String(value || ""));
		return String(value || "").replace(/[&<>"']/g, (char) => ({
			"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
		})[char]);
	}

	}

	boot();
})();

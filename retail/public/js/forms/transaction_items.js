(function () {
	if (window.__retail_transaction_items_booted) return;
	window.__retail_transaction_items_booted = true;

	function boot() {
		if (!window.frappe?.ui?.form) {
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
				syncVatRates(frm, cdt, cdn, "rate");
				scheduleVatSync(frm, cdt, cdn, "rate");
				scheduleVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
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
			net_rate(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			item_tax_template(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			tax_rate(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
			},
			qty(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "qty");
				queueVatTaxRowsSync(frm);
				renderTransactionTotals(frm);
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

	Object.keys(liveVatFormDoctypes).forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				placeVatFieldBeforeGrandTotal(frm);
			},
			company(frm) {
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
		[250, 700].forEach((delay) => {
			setTimeout(() => queueVatTaxRowsSync(frm), delay);
		});
	}

	function scheduleVatSync(frm, cdt, cdn, source) {
		[150, 500].forEach((delay) => {
			setTimeout(() => {
				if (!locals[cdt]?.[cdn]) return;
				syncVatRates(frm, cdt, cdn, source);
			}, delay);
		});
	}

	async function syncVatRates(frm, cdt, cdn, source) {
		if (!isEditableDraft(frm)) return;

		const row = locals[cdt]?.[cdn];
		if (!row || row.__retail_vat_syncing || !row.item_code) return;
		if (!frappe.meta.get_docfield(cdt, "custom_rate_including_vat", cdn)) return;

		row.__retail_vat_syncing = true;
		try {
			const vatRate = await getVatRate(frm, row, cdt);
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
				if (exclusiveRate) {
					inclusiveRate = flt(exclusiveRate * factor, precision);
					values.rate = flt(exclusiveRate, precision);
					values.custom_rate_including_vat = inclusiveRate;
				}
				if (amountField) {
					values.amount = flt(qty * exclusiveRate, amountPrecision);
				}
			}

			if (source !== "inclusive_amount" && row.custom_amount_including_vat !== undefined) {
				values.custom_amount_including_vat = flt(qty * inclusiveRate, amountPrecision);
			}

			if (!Object.keys(values).length) return;
			await setRowValues(frm, cdt, cdn, values);
			queueVatTaxRowsSync(frm);
			renderTransactionTotals(frm);
		} finally {
			if (row) row.__retail_vat_syncing = false;
		}
	}

	function queueVatTaxRowsSync(frm) {
		if (!canSyncVatTaxRows(frm)) return;

		clearTimeout(frm.__retail_vat_tax_rows_timer);
		frm.__retail_vat_tax_rows_timer = setTimeout(() => {
			syncVatTaxRows(frm);
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

	async function syncVatTaxRows(frm) {
		if (!canSyncVatTaxRows(frm) || frm.__retail_syncing_vat_tax_rows) return;

		frm.__retail_syncing_vat_tax_rows = true;
		try {
			const response = await frappe.call({
				method: "retail.domains.transactions.vat.get_transaction_vat_tax_rows",
				args: {
					doc: frm.doc,
				},
			});
			const setup = normalizeVatTaxSetup(response.message);
			applyItemTaxRates(frm, setup.item_tax_rates);
			replaceManagedVatTaxRows(frm, setup.tax_rows);
			await runErpnextTotals(frm);
			placeVatFieldBeforeGrandTotal(frm);
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
		managedRows.forEach((row) => frappe.model.clear_doc(row.doctype, row.name));
		frm.doc.taxes = taxTable.filter((row) => !isManagedVatTaxRow(row, taxLabel));

		taxRows.forEach((values) => {
			const row = frm.add_child("taxes");
			Object.assign(row, values);
		});

		refreshTaxTable(frm);
	}

	async function runErpnextTotals(frm) {
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

	async function setRowValues(frm, cdt, cdn, values) {
		for (const [fieldname, value] of Object.entries(values)) {
			await frappe.model.set_value(cdt, cdn, fieldname, value);
		}
		const gridRow = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[cdn];
		Object.keys(values).forEach((fieldname) => gridRow?.refresh_field?.(fieldname));
	}

	function getExclusiveRateForVat(row, qty) {
		if (hasEnteredValue(row.rate) && flt(row.rate)) return flt(row.rate);
		if (qty && hasEnteredValue(row.amount) && flt(row.amount)) return flt(row.amount) / qty;
		if (hasEnteredValue(row.net_rate) && flt(row.net_rate)) return flt(row.net_rate);
		if (hasEnteredValue(row.price_list_rate) && flt(row.price_list_rate)) return flt(row.price_list_rate);
		return flt(row.rate);
	}

	async function getVatRate(frm, row, childDoctype) {
		const parentDoc = frm?.doc || {};
		const rowRate = flt(row.tax_rate);
		const formRate = getFormTaxRate(frm);
		if (rowRate) return rowRate;

		const response = await frappe.call({
			method: "retail.domains.transactions.vat.get_transaction_item_vat_rate",
			args: {
				item_code: row.item_code,
				child_doctype: childDoctype,
				parent_doctype: parentDoc.doctype,
				transaction_type: parentDoc.transaction_type,
				item_tax_template: row.item_tax_template,
			},
		});
		return flt(response.message) || formRate;
	}

	function getFormTaxRate(frm) {
		const rates = (frm.doc.taxes || [])
			.map((row) => flt(row.rate))
			.filter((rate) => rate > 0 && rate < 100);
		const uniqueRates = [...new Set(rates)];
		if (uniqueRates.length === 1) return uniqueRates[0];

		const templateRate = String(frm.doc.taxes_and_charges || "").match(/(\d+(?:\.\d+)?)\s*%/);
		return templateRate ? flt(templateRate[1]) : 0;
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

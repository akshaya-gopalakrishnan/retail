(function () {
	if (!window.frappe?.ui?.form) return;

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

	const totalsFormDoctypes = {
		"Purchase Order": "Purchase Tax",
		"Purchase Receipt": "Purchase Tax",
		"Purchase Invoice": "Purchase Tax",
		"Sales Order": "Sales Tax",
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
				renderTransactionTotals(frm);
			},
			rate(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
				renderTransactionTotals(frm);
			},
			qty(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "qty");
				renderTransactionTotals(frm);
			},
			custom_rate_including_vat(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "inclusive");
				renderTransactionTotals(frm);
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
			custom_amount_including_vat(frm) {
				renderTransactionTotals(frm);
			},
			amount(frm) {
				renderTransactionTotals(frm);
			},
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
	bindEditableGridClose();

	async function syncVatRates(frm, cdt, cdn, source) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.__retail_vat_syncing || !row.item_code) return;
		if (row.custom_rate_including_vat === undefined) return;

		row.__retail_vat_syncing = true;
		try {
			const vatRate = await getVatRate(frm, row.item_code, cdt);
			const factor = 1 + (flt(vatRate) / 100);
			const precision = cint(frappe.meta.get_docfield(cdt, "rate", cdn)?.precision) || 2;
			const amountPrecision = cint(frappe.meta.get_docfield(cdt, "amount", cdn)?.precision) || precision;
			const values = {};
			let inclusiveRate = flt(row.custom_rate_including_vat);

			if (source === "inclusive") {
				const exclusiveRate = factor ? inclusiveRate / factor : inclusiveRate;
				values.rate = flt(exclusiveRate, precision);
			} else {
				const exclusiveRate = flt(row.rate);
				if (exclusiveRate) {
					inclusiveRate = flt(exclusiveRate * factor, precision);
					values.custom_rate_including_vat = inclusiveRate;
				}
			}

			if (row.custom_amount_including_vat !== undefined) {
				values.custom_amount_including_vat = flt(flt(row.qty) * inclusiveRate, amountPrecision);
			}

			if (!Object.keys(values).length) return;
			await frappe.model.set_value(cdt, cdn, values);
		} finally {
			if (row) row.__retail_vat_syncing = false;
		}
	}

	async function getVatRate(frm, itemCode, childDoctype) {
		const parentDoc = frm?.doc || {};
		const response = await frappe.call({
			method: "retail.domains.transactions.vat.get_transaction_item_vat_rate",
			args: {
				item_code: itemCode,
				child_doctype: childDoctype,
				parent_doctype: parentDoc.doctype,
				transaction_type: parentDoc.transaction_type,
			},
		});
		return flt(response.message);
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
		if (hasEnteredValue(row.custom_rate_including_vat)) {
			return flt(row.qty) * flt(row.custom_rate_including_vat);
		}
		if (hasEnteredValue(row.custom_amount_including_vat)) {
			return flt(row.custom_amount_including_vat);
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

	function bindEditableGridClose() {
		if (window.__retail_grid_close_bound) return;
		window.__retail_grid_close_bound = true;

		document.addEventListener(
			"keydown",
			(event) => {
				if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) {
					return;
				}
				const row = frappe.ui.form.editable_row;
				if (!row || !row.wrapper?.get(0)?.contains(event.target)) return;
				if (isAutocompleteOpen(event.target)) return;

				setTimeout(() => closeEditableRow(row), 0);
			},
			true
		);

		document.addEventListener(
			"mousedown",
			(event) => {
				const row = frappe.ui.form.editable_row;
				if (!row) return;

				const target = event.target;
				if (row.wrapper?.get(0)?.contains(target)) return;
				if (target.closest(".awesomplete, .modal, .datepicker, .flatpickr-calendar")) return;

				closeEditableRow(row);
			},
			true
		);
	}

	function closeEditableRow(row) {
		if (!row) return;
		if (row.doc?.__retail_vat_syncing) {
			setTimeout(() => closeEditableRow(row), 50);
			return;
		}
		row.toggle_editable_row(false);
	}

	function isAutocompleteOpen(target) {
		const wrapper = target.closest(".awesomplete");
		if (!wrapper) return false;
		const list = wrapper.querySelector("ul");
		return Boolean(list && list.children.length && !list.hidden);
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
})();

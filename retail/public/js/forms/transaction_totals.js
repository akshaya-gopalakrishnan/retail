(function () {
	if (!window.frappe?.ui?.form) return;

	const formDoctypes = {
		"Purchase Order": "Purchase Tax",
		"Purchase Receipt": "Purchase Tax",
		"Purchase Invoice": "Purchase Tax",
		"Sales Order": "Sales Tax",
	};

	Object.keys(formDoctypes).forEach((doctype) => {
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

	const itemDoctypes = [
		"Purchase Order Item",
		"Purchase Receipt Item",
		"Purchase Invoice Item",
		"Sales Order Item",
	];

	itemDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			item_code(frm) {
				renderTransactionTotals(frm);
			},
			qty(frm) {
				renderTransactionTotals(frm);
			},
			rate(frm) {
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
		if (!formDoctypes[frm.doctype]) return;

		const field = frm.fields_dict.custom_retail_totals_summary;
		if (!field) return;
		applyTotalsLayout(field);

		const currency = frm.doc.currency;
		const subtotal = getSubtotal(frm);
		const tax = getTaxAmount(frm);
		const total = hasEnteredValue(frm.doc.grand_total)
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
		const itemSubtotal = (frm.doc.items || []).reduce((total, row) => {
			const amount = hasEnteredValue(row.net_amount) ? row.net_amount : row.amount;
			if (hasEnteredValue(amount)) return total + flt(amount);
			return total + flt(row.qty) * flt(row.rate);
		}, 0);

		return flt(itemSubtotal || frm.doc.net_total || frm.doc.total || frm.doc.base_net_total || frm.doc.base_total);
	}

	function getTaxAmount(frm) {
		const rowTax = (frm.doc.taxes || []).reduce((total, row) => {
			const amount = row.tax_amount_after_discount_amount ?? row.tax_amount;
			return total + flt(amount);
		}, 0);

		if (rowTax) return rowTax;
		return flt(frm.doc.total_taxes_and_charges);
	}

	function getTaxLabel(frm) {
		const template = frm.doc.taxes_and_charges;
		if (template) return __("{0} [{1}]", [formDoctypes[frm.doctype], template]);

		const taxRows = frm.doc.taxes || [];
		const rates = [...new Set(taxRows.map((row) => flt(row.rate)).filter((rate) => rate))];
		if (rates.length === 1) return __("{0} [{1}%]", [formDoctypes[frm.doctype], rates[0]]);

		const description = taxRows.map((row) => row.description).filter(Boolean)[0];
		return description ? __("{0} [{1}]", [formDoctypes[frm.doctype], description]) : __(formDoctypes[frm.doctype]);
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

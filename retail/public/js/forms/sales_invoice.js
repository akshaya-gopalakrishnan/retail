(function () {
	if (!window.frappe?.ui?.form) return;

	const SHIPPING_DESCRIPTION = "Shipping Charges";

	frappe.ui.form.on("Sales Invoice", {
		onload_post_render(frm) {
			keepCompanyVisible(frm);
		},
		refresh(frm) {
			keepCompanyVisible(frm);
			refreshRetailTotals(frm);
		},
		net_total(frm) {
			refreshRetailTotals(frm);
		},
		total_taxes_and_charges(frm) {
			refreshRetailTotals(frm);
		},
		grand_total(frm) {
			refreshRetailTotals(frm);
		},
		rounded_total(frm) {
			refreshRetailTotals(frm);
		},
		taxes_and_charges(frm) {
			refreshRetailTotals(frm);
		},
		custom_retail_shipping_charges(frm) {
			refreshRetailTotals(frm);
		},
	});

	function keepCompanyVisible(frm) {
		if (!frm?.fields_dict?.company) return;

		const showCompany = () => {
			if (!frm.fields_dict.company) return;
			frm.set_df_property("company", "hidden", 0);
			frm.fields_dict.company.df.hidden = 0;
			frm.toggle_display("company", true);
			frm.refresh_field("company");
		};

		showCompany();
		frappe.after_ajax(showCompany);
		setTimeout(showCompany, 0);
		setTimeout(showCompany, 250);
	}

	frappe.ui.form.on("Sales Invoice Item", {
		item_code(frm) {
			refreshRetailTotals(frm);
		},
		qty(frm, cdt, cdn) {
			updateFocQty(frm, cdt, cdn);
			refreshRetailTotals(frm);
		},
		rate(frm) {
			refreshRetailTotals(frm);
		},
		amount(frm) {
			refreshRetailTotals(frm);
		},
		item_tax_template(frm) {
			refreshRetailTotals(frm);
		},
		conversion_factor(frm, cdt, cdn) {
			updateFocQty(frm, cdt, cdn);
		},
		custom_foc_qty(frm, cdt, cdn) {
			updateFocQty(frm, cdt, cdn);
			refreshRetailTotals(frm);
		},
		items_remove(frm) {
			refreshRetailTotals(frm);
		},
	});

	frappe.ui.form.on("Sales Taxes and Charges", {
		tax_amount_after_discount_amount(frm) {
			refreshRetailTotals(frm);
		},
		rate(frm) {
			refreshRetailTotals(frm);
		},
		description(frm) {
			refreshRetailTotals(frm);
		},
	});

	function refreshRetailTotals(frm) {
		renderRetailTotals(frm);
		refreshItemTaxRates(frm).then((changed) => {
			if (changed) renderRetailTotals(frm);
		});
	}

	function renderRetailTotals(frm) {
		const field = frm.fields_dict.custom_retail_totals_summary;
		if (!field) return;
		applyRetailTotalsLayout(field);

		const currency = frm.doc.currency;
		const subtotal = getSubtotal(frm);
		const shipping = getShippingAmount(frm);
		const salesTax = getSalesTaxAmount(frm);
		const total = subtotal + salesTax + shipping;

		field.$wrapper.html(`
			<style>
				.retail-si-totals {
					border-top: 1px solid var(--border-color);
					margin-top: 8px;
					max-width: 100%;
				}
				.retail-si-totals-section > .section-body {
					align-items: flex-start;
					display: flex;
				}
				.retail-si-totals-section > .section-body > .retail-si-spacer-column {
					display: none !important;
				}
				.retail-si-totals-section > .section-body > .retail-si-quantity-column {
					flex: 0 0 32% !important;
					max-width: 32% !important;
				}
				.retail-si-totals-section > .section-body > .retail-si-totals-column {
					flex: 0 0 50% !important;
					margin-left: auto;
					max-width: 50% !important;
				}
				@media (max-width: 767.98px) {
					.retail-si-totals-section > .section-body {
						display: block;
					}
					.retail-si-totals-section > .section-body > .retail-si-quantity-column,
					.retail-si-totals-section > .section-body > .retail-si-totals-column {
						flex: 0 0 100% !important;
						max-width: 100% !important;
					}
				}
				.retail-si-total-row {
					align-items: center;
					border-bottom: 1px solid var(--border-color);
					display: grid;
					grid-template-columns: minmax(0, 1fr) auto;
					gap: 16px;
					min-height: 42px;
					padding: 8px 4px;
				}
				.retail-si-total-row.total {
					background: var(--subtle-fg);
					font-weight: 700;
					padding-left: 8px;
					padding-right: 8px;
				}
				.retail-si-total-label {
					color: var(--text-muted);
					overflow-wrap: anywhere;
				}
				.retail-si-total-row.total .retail-si-total-label,
				.retail-si-total-row.total .retail-si-total-value {
					color: var(--primary);
				}
				.retail-si-total-value {
					font-variant-numeric: tabular-nums;
					text-align: right;
				}
			</style>
			<div class="retail-si-totals">
				${getTotalRow(__("Sub Total"), subtotal, currency)}
				${getTotalRow(getSalesTaxLabel(frm), salesTax, currency)}
				${getTotalRow(__("Shipping Charges"), shipping, currency)}
				${getTotalRow(__("Total ({0})", [currency || ""] ), total, currency, true)}
			</div>
		`);
	}

	function applyRetailTotalsLayout(field) {
		const section = field.$wrapper.closest(".form-section");
		if (!section?.length) return;

		const columns = section.children(".section-body").children(".form-column");
		const totalsColumn = field.$wrapper.closest(".form-column");
		const quantityColumn = columns
			.filter((_, column) => $(column).find('[data-fieldname="total_qty"]').length)
			.first();

		section.addClass("retail-si-totals-section");
		columns.removeClass("retail-si-quantity-column retail-si-totals-column retail-si-spacer-column");

		quantityColumn.addClass("retail-si-quantity-column");
		totalsColumn.addClass("retail-si-totals-column");
		columns.not(quantityColumn).not(totalsColumn).addClass("retail-si-spacer-column");
	}

	function getTotalRow(label, value, currency, isTotal) {
		return `
			<div class="retail-si-total-row ${isTotal ? "total" : ""}">
				<div class="retail-si-total-label">${escapeHtml(label)}</div>
				<div class="retail-si-total-value">${format_currency(value, currency)}</div>
			</div>
		`;
	}

	function getSalesTaxLabel(frm) {
		const template = frm.doc.taxes_and_charges;
		if (template) return __("Sales Tax [{0}]", [template]);

		const taxRows = getSalesTaxRows(frm);
		const rates = [...new Set(taxRows.map((row) => flt(row.rate)).filter((rate) => rate))];
		if (rates.length === 1) return __("Sales Tax [{0}%]", [rates[0]]);

		const itemTemplates = getItemTaxTemplates(frm);
		if (itemTemplates.length === 1) return __("Sales Tax [{0}]", [itemTemplates[0]]);

		const itemRates = [...new Set(getItemTaxRates(frm).filter((rate) => rate))];
		if (itemRates.length === 1) return __("Sales Tax [{0}%]", [itemRates[0]]);

		const description = taxRows.map((row) => row.description).filter(Boolean)[0];
		return description ? __("Sales Tax [{0}]", [description]) : __("Sales Tax");
	}

	function getSalesTaxAmount(frm) {
		const rowTax = getSalesTaxRows(frm).reduce((total, row) => {
			const amount = row.tax_amount_after_discount_amount ?? row.tax_amount;
			return total + flt(amount);
		}, 0);

		if (rowTax) return rowTax;

		const totalTaxes = flt(frm.doc.total_taxes_and_charges);
		const standardTax = Math.max(totalTaxes - getShippingAmountFromTaxRows(frm), 0);
		if (standardTax) return standardTax;

		return getEstimatedItemSalesTax(frm);
	}

	function getSalesTaxRows(frm) {
		return (frm.doc.taxes || []).filter((row) => !isShippingRow(row));
	}

	function getShippingAmount(frm) {
		if (hasEnteredValue(frm.doc.custom_retail_shipping_charges)) {
			return flt(frm.doc.custom_retail_shipping_charges);
		}

		return getShippingAmountFromTaxRows(frm);
	}

	function getShippingAmountFromTaxRows(frm) {
		return (frm.doc.taxes || []).reduce((total, row) => {
			if (!isShippingRow(row)) return total;
			const amount = row.tax_amount_after_discount_amount ?? row.tax_amount;
			return total + flt(amount);
		}, 0);
	}

	function getSubtotal(frm) {
		const itemSubtotal = (frm.doc.items || []).reduce((total, row) => {
			const amount = hasEnteredValue(row.net_amount) ? row.net_amount : row.amount;
			if (hasEnteredValue(amount)) return total + flt(amount);
			return total + flt(row.qty) * flt(row.rate);
		}, 0);

		return flt(itemSubtotal || frm.doc.net_total || frm.doc.total || frm.doc.base_net_total || frm.doc.base_total);
	}

	function getEstimatedItemSalesTax(frm) {
		return (frm.doc.items || []).reduce((total, row) => {
			const amount = hasEnteredValue(row.net_amount) ? row.net_amount : row.amount;
			const baseAmount = hasEnteredValue(amount) ? flt(amount) : flt(row.qty) * flt(row.rate);
			return total + (baseAmount * getItemTaxRate(frm, row)) / 100;
		}, 0);
	}

	function getItemTaxRate(frm, row) {
		const template = getRowTaxTemplate(frm, row);
		return template ? flt(frm._retail_item_tax_rates?.[template]) : 0;
	}

	function getItemTaxRates(frm) {
		return (frm.doc.items || []).map((row) => getItemTaxRate(frm, row));
	}

	function getItemTaxTemplates(frm) {
		const templates = (frm.doc.items || []).map((row) => getRowTaxTemplate(frm, row)).filter(Boolean);
		return [...new Set(templates)];
	}

	function getRowTaxTemplate(frm, row) {
		return row.item_tax_template || frm._retail_item_tax_templates?.[row.item_code];
	}

	function refreshItemTaxRates(frm) {
		frm._retail_item_tax_rates = frm._retail_item_tax_rates || {};
		frm._retail_item_tax_templates = frm._retail_item_tax_templates || {};

		const templateTasks = [];
		const itemTasks = [];

		(frm.doc.items || []).forEach((row) => {
			if (row.item_tax_template) {
				templateTasks.push(fetchTaxRate(frm, row.item_tax_template));
				return;
			}

			if (!row.item_code || frm._retail_item_tax_templates[row.item_code] !== undefined) return;

			itemTasks.push(
				frappe.db.get_value("Item", row.item_code, "custom_tax").then(({ message }) => {
					frm._retail_item_tax_templates[row.item_code] = message?.custom_tax || "";
					if (message?.custom_tax) return fetchTaxRate(frm, message.custom_tax);
					return null;
				})
			);
		});

		if (!templateTasks.length && !itemTasks.length) return Promise.resolve(false);
		return Promise.all([...templateTasks, ...itemTasks]).then(() => true);
	}

	function fetchTaxRate(frm, template) {
		if (!template || frm._retail_item_tax_rates[template] !== undefined) return Promise.resolve();

		return frappe.call({
			method: "retail.domains.item.vat_pricing.get_item_tax_rate",
			args: { template },
		}).then(({ message }) => {
			frm._retail_item_tax_rates[template] = flt(message || 0);
		});
	}

	function isShippingRow(row) {
		return (row.description || "").trim().toLowerCase() === SHIPPING_DESCRIPTION.toLowerCase();
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

	function updateFocQty(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.custom_total_stock_qty === undefined) return;

		const totalQty = flt(row.qty) + flt(row.custom_foc_qty);
		const values = {
			custom_total_stock_qty: totalQty,
		};

		frappe.model.set_value(cdt, cdn, values);
		frm.refresh_field("items");
	}
	})();

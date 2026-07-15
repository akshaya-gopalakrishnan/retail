(function () {
	if (!window.frappe?.ui?.form) return;

	const parentDoctypes = ["Purchase Receipt", "Purchase Invoice"];
	const itemDoctypes = ["Purchase Receipt Item", "Purchase Invoice Item"];

	parentDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				toggleSellPriceColumns(frm);
				alignAllowSellingPrice(frm);
				addSellPriceButtons(frm);
				addItemRateUpdateButton(frm);
				refreshAllRows(frm);
			},
			custom_allow_selling_price(frm) {
				toggleSellPriceColumns(frm);
				return setAllSellPriceUpdates(frm, frm.doc.custom_allow_selling_price ? 1 : 0);
			},
			before_submit(frm) {
				confirmSellPriceUpdates(frm);
			},
		});
	});

	itemDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			item_code(frm, cdt, cdn) {
				enableRowSellPriceWhenAllowed(frm, cdt, cdn);
				fetchCurrentSellingRate(frm, cdt, cdn);
			},
			uom(frm, cdt, cdn) {
				fetchCurrentSellingRate(frm, cdt, cdn);
			},
			rate(frm, cdt, cdn) {
				updateMargin(frm, cdt, cdn);
			},
			net_rate(frm, cdt, cdn) {
				updateMargin(frm, cdt, cdn);
			},
			async custom_upd_sell_price(frm, cdt, cdn) {
				const row = locals[cdt]?.[cdn];
				if (!row) return;

				if (row.custom_upd_sell_price && !flt(row.custom_cur_sell_rate)) {
					await fetchCurrentSellingRate(frm, cdt, cdn);
				}
				const values = {};
				if (row.custom_upd_sell_price && !flt(row.custom_new_sell_rate)) {
					values.custom_new_sell_rate = flt(row.custom_cur_sell_rate);
				}
				if (Object.keys(values).length) {
					await frappe.model.set_value(cdt, cdn, values);
				}
				await updateInclusiveRate(frm, cdt, cdn);
				updateMargin(frm, cdt, cdn);
			},
			custom_new_sell_rate(frm, cdt, cdn) {
				updateInclusiveRate(frm, cdt, cdn).then(() => updateMargin(frm, cdt, cdn));
			},
			custom_new_sell_incl(frm, cdt, cdn) {
				updateExclusiveRate(frm, cdt, cdn).then(() => updateMargin(frm, cdt, cdn));
			},
		});
	});

	function addSellPriceButtons(frm) {
		if (!parentDoctypes.includes(frm.doctype) || frm.doc.docstatus !== 0) return;
		if (!hasSellPriceFields(frm)) return;
		if (!frm.doc.custom_allow_selling_price) return;

		frm.add_custom_button(__("Tick All"), () => setAllSellPriceUpdates(frm, 1), __("Sell Price"));
		frm.add_custom_button(__("Untick All"), () => setAllSellPriceUpdates(frm, 0), __("Sell Price"));
	}

	function addItemRateUpdateButton(frm) {
		if (!parentDoctypes.includes(frm.doctype) || frm.doc.docstatus !== 1) return;
		frm.add_custom_button(__("Update Item Master Rates"), () => updateItemMasterRates(frm), __("Retail"));
	}

	async function updateItemMasterRates(frm) {
		const preview = (await frappe.call({
			method: "retail.domains.item.rate_audit.get_purchase_document_rate_preview",
			args: {
				source_doctype: frm.doctype,
				source_name: frm.doc.name,
			},
		})).message || [];

		if (!preview.length) {
			frappe.msgprint(__("No Item Master purchase rate changes found."));
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Update Item Master Purchase Rates"),
			size: "extra-large",
			fields: [
				{ fieldtype: "HTML", fieldname: "preview_html" },
			],
			primary_action_label: __("Confirm Update"),
			primary_action: async () => {
				const selectedRows = getSelectedPreviewRows(dialog);
				if (!selectedRows.length) {
					frappe.msgprint(__("Select at least one item row."));
					return;
				}
				const result = await frappe.call({
					method: "retail.domains.item.rate_audit.apply_purchase_document_rate_updates",
					args: {
						source_doctype: frm.doctype,
						source_name: frm.doc.name,
						source_rows: selectedRows,
					},
					freeze: true,
					freeze_message: __("Updating Item Master Rates"),
				});
				dialog.hide();
				frappe.show_alert({
					message: __("Updated {0} Item Master rate(s)", [(result.message || []).length]),
					indicator: "green",
				});
			},
		});

		dialog.fields_dict.preview_html.$wrapper.html(getPreviewHtml(preview));
		dialog.show();
	}

	function getSelectedPreviewRows(dialog) {
		return dialog.fields_dict.preview_html.$wrapper
			.find("input[data-source-row]:checked")
			.map((_, input) => input.dataset.sourceRow)
			.get();
	}

	function getPreviewHtml(rows) {
		const body = rows.map((row) => `
			<tr>
				<td><input type="checkbox" data-source-row="${escapeHtml(row.source_row)}" checked></td>
				<td>${escapeHtml(row.item_code)}</td>
				<td>${escapeHtml(row.uom || "")}</td>
				<td class="text-right">${format_currency(row.old_net_rate)}</td>
				<td class="text-right">${format_currency(row.new_net_rate)}</td>
				<td class="text-right">${format_currency(row.new_gross_rate)}</td>
			</tr>
		`).join("");

		return `
			<p class="text-muted">
				${__("This will change official Item Master purchase rates for future packing and pricing calculations. The action is audited with your user name.")}
			</p>
			<table class="table table-bordered">
				<thead>
					<tr>
						<th style="width: 40px"></th>
						<th>${__("Item")}</th>
						<th>${__("UOM")}</th>
						<th class="text-right">${__("Old Excl. VAT")}</th>
						<th class="text-right">${__("New Excl. VAT")}</th>
						<th class="text-right">${__("New Incl. VAT")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`;
	}

	function hasSellPriceFields(frm) {
		const grid = frm.fields_dict.items?.grid;
		return Boolean(grid?.fields_map?.custom_upd_sell_price);
	}

	function toggleSellPriceColumns(frm) {
		if (!hasSellPriceFields(frm)) return;

		const show = Boolean(frm.doc.custom_allow_selling_price);
		const fields = [
			"custom_cur_sell_rate",
			"custom_new_sell_rate",
			"custom_new_sell_incl",
		];
		if (frm.doctype !== "Purchase Receipt") {
			fields.push("custom_sell_margin");
		}

		fields.forEach((fieldname) => {
			frm.fields_dict.items.grid.update_docfield_property(fieldname, "hidden", !show);
		});
		frm.fields_dict.items.grid.update_docfield_property("custom_new_sell_rate", "read_only", !show);
		frm.fields_dict.items.grid.update_docfield_property("custom_new_sell_rate", "depends_on", "");
		frm.fields_dict.items.grid.update_docfield_property("custom_new_sell_incl", "read_only", !show);
		frm.fields_dict.items.grid.update_docfield_property("custom_new_sell_incl", "depends_on", "");
		if (frm.doctype === "Purchase Receipt") {
			frm.fields_dict.items.grid.update_docfield_property("custom_sell_margin", "hidden", true);
		}
		frm.refresh_field("items");
	}

	function alignAllowSellingPrice(frm) {
		const field = frm.fields_dict.custom_allow_selling_price;
		if (!field?.$wrapper) return;

		field.$wrapper.addClass("retail-allow-selling-price-right");
		if (document.getElementById("retail-allow-selling-price-style")) return;

		$(`<style id="retail-allow-selling-price-style">
			.retail-allow-selling-price-right .checkbox {
				display: flex;
				justify-content: flex-end;
			}
			.retail-allow-selling-price-right .checkbox label {
				margin-right: 0;
			}
		</style>`).appendTo(document.head);
	}

	function refreshAllRows(frm) {
		if (!hasSellPriceFields(frm)) return;
		if (!frm.doc.custom_allow_selling_price) return;
		(frm.doc.items || []).forEach((row) => {
			if (row.item_code && !flt(row.custom_cur_sell_rate)) {
				fetchCurrentSellingRate(frm, row.doctype, row.name);
			} else {
				updateMargin(frm, row.doctype, row.name);
			}
		});
	}

	async function setAllSellPriceUpdates(frm, value) {
		const rows = frm.doc.items || [];
		for (const row of rows) {
			if (!row.item_code) continue;
			if (value && !flt(row.custom_cur_sell_rate)) {
				await fetchCurrentSellingRate(frm, row.doctype, row.name);
			}
			const values = { custom_upd_sell_price: value };
			if (value && !flt(row.custom_new_sell_rate)) {
				values.custom_new_sell_rate = flt(row.custom_cur_sell_rate);
			}
			await frappe.model.set_value(row.doctype, row.name, values);
			await updateInclusiveRate(frm, row.doctype, row.name);
			updateMargin(frm, row.doctype, row.name);
		}
		frm.refresh_field("items");
	}

	function enableRowSellPriceWhenAllowed(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row?.item_code || !frm.doc.custom_allow_selling_price) return;
		if (!row.custom_upd_sell_price) {
			frappe.model.set_value(cdt, cdn, "custom_upd_sell_price", 1);
		}
	}

	async function fetchCurrentSellingRate(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row?.item_code || row.custom_cur_sell_rate === undefined) return;

		const response = await frappe.call({
			method: "retail.domains.purchase.selling_price.get_standard_selling_rate",
			args: {
				item_code: row.item_code,
				uom: row.uom,
			},
		});
		const rate = flt(response.message);
		const values = { custom_cur_sell_rate: rate };
		if (row.custom_upd_sell_price && !flt(row.custom_new_sell_rate)) {
			values.custom_new_sell_rate = rate;
		}
		await frappe.model.set_value(cdt, cdn, values);
		await updateInclusiveRate(frm, cdt, cdn);
		updateMargin(frm, cdt, cdn);
	}

	async function updateInclusiveRate(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.__retail_sell_price_syncing || row.custom_new_sell_incl === undefined) return;

		const exclusiveRate = flt(row.custom_new_sell_rate || row.custom_cur_sell_rate);
		const vatRate = await getSellingVatRate(frm, row);
		if (!locals[cdt]?.[cdn] || locals[cdt][cdn].item_code !== row.item_code) return;

		row.__retail_sell_price_syncing = true;
		try {
			await frappe.model.set_value(cdt, cdn, {
				custom_new_sell_incl: flt(exclusiveRate * (1 + vatRate / 100), 2),
			});
		} finally {
			row.__retail_sell_price_syncing = false;
		}
	}

	async function updateExclusiveRate(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.__retail_sell_price_syncing || row.custom_new_sell_incl === undefined) return;

		const inclusiveRate = flt(row.custom_new_sell_incl);
		const vatRate = await getSellingVatRate(frm, row);
		if (!locals[cdt]?.[cdn] || locals[cdt][cdn].item_code !== row.item_code) return;

		const divisor = 1 + vatRate / 100;
		row.__retail_sell_price_syncing = true;
		try {
			await frappe.model.set_value(cdt, cdn, {
				custom_new_sell_rate: divisor ? flt(inclusiveRate / divisor, 2) : inclusiveRate,
			});
		} finally {
			row.__retail_sell_price_syncing = false;
		}
	}

	async function getSellingVatRate(frm, row) {
		const itemCode = row?.item_code;
		if (!itemCode) return 0;

		const response = await frappe.call({
			method: "retail.domains.purchase.selling_price.get_item_selling_vat_rate",
			args: { item_code: itemCode },
		});
		return flt(response.message) || getPurchaseFormVatRate(frm, row);
	}

	function getPurchaseFormVatRate(frm, row) {
		const taxRate = getRowItemTaxRate(row);
		if (taxRate) return taxRate;

		const rates = (frm.doc.taxes || []).map((tax) => flt(tax.rate)).filter((rate) => rate);
		const uniqueRates = [...new Set(rates)];
		if (uniqueRates.length === 1) return uniqueRates[0];

		const amount = flt(row?.amount || row?.net_amount || flt(row?.qty) * flt(row?.rate));
		const taxAmount = flt(frm.doc.total_taxes_and_charges);
		return amount && taxAmount ? flt((taxAmount / amount) * 100, 3) : 0;
	}

	function getRowItemTaxRate(row) {
		if (!row?.item_tax_rate) return 0;

		try {
			const rates = Object.values(JSON.parse(row.item_tax_rate)).map((rate) => flt(rate)).filter((rate) => rate);
			const uniqueRates = [...new Set(rates)];
			return uniqueRates.length === 1 ? uniqueRates[0] : 0;
		} catch (e) {
			return 0;
		}
	}

	function updateMargin(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.custom_new_sell_rate === undefined) return;

		const sellingRate = flt(row.custom_new_sell_rate || row.custom_cur_sell_rate);
		const purchaseRate = flt(row.rate || row.net_rate);
		const margin = sellingRate ? sellingRate - purchaseRate : 0;
		const marginPercent = sellingRate ? (margin / sellingRate) * 100 : 0;

		frappe.model.set_value(cdt, cdn, {
			custom_sell_margin: flt(margin, 2),
			custom_sell_margin_pct: flt(marginPercent, 3),
		});
		frm.refresh_field("items");
	}

	function confirmSellPriceUpdates(frm) {
		if (frm.__retail_sell_price_confirmed) return;
		if (!frm.doc.custom_allow_selling_price) return;

		const rows = (frm.doc.items || []).filter(
			(row) => row.custom_upd_sell_price
				&& flt(row.custom_new_sell_rate) > 0
				&& flt(row.custom_new_sell_rate) !== flt(row.custom_cur_sell_rate)
		);
		if (!rows.length) return;

		frappe.validated = false;
		frappe.confirm(
			__("Update Standard Selling price for {0} selected item row(s)?", [rows.length]),
			() => {
				frm.__retail_sell_price_confirmed = true;
				frm.savesubmit();
			}
		);
	}

	function escapeHtml(value) {
		if (frappe.utils?.escape_html) return frappe.utils.escape_html(String(value || ""));
		return String(value || "").replace(/[&<>"']/g, (char) => ({
			"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
		})[char]);
	}
})();

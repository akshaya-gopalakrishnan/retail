(function () {
	if (!window.frappe?.ui?.form) return;

	const parentDoctypes = ["Purchase Receipt", "Purchase Invoice"];
	const itemDoctypes = ["Purchase Receipt Item", "Purchase Invoice Item"];

	parentDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				addSellPriceButtons(frm);
				refreshAllRows(frm);
			},
			before_submit(frm) {
				confirmSellPriceUpdates(frm);
			},
		});
	});

	itemDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			item_code(frm, cdt, cdn) {
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

		frm.add_custom_button(__("Tick All"), () => setAllSellPriceUpdates(frm, 1), __("Sell Price"));
		frm.add_custom_button(__("Untick All"), () => setAllSellPriceUpdates(frm, 0), __("Sell Price"));
	}

	function hasSellPriceFields(frm) {
		const grid = frm.fields_dict.items?.grid;
		return Boolean(grid?.fields_map?.custom_upd_sell_price);
	}

	function refreshAllRows(frm) {
		if (!hasSellPriceFields(frm)) return;
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
		const vatRate = await getSellingVatRate(row.item_code);
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
		const vatRate = await getSellingVatRate(row.item_code);
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

	async function getSellingVatRate(itemCode) {
		if (!itemCode) return 0;
		window.__retail_purchase_sell_vat = window.__retail_purchase_sell_vat || {};
		if (window.__retail_purchase_sell_vat[itemCode] !== undefined) {
			return flt(window.__retail_purchase_sell_vat[itemCode]);
		}

		const response = await frappe.call({
			method: "retail.domains.purchase.selling_price.get_item_selling_vat_rate",
			args: { item_code: itemCode },
		});
		window.__retail_purchase_sell_vat[itemCode] = flt(response.message);
		return flt(response.message);
	}

	function updateMargin(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.custom_new_sell_rate === undefined) return;

		const sellingRate = flt(row.custom_new_sell_rate || row.custom_cur_sell_rate);
		const purchaseRate = flt(row.net_rate || row.rate);
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

		const rows = (frm.doc.items || []).filter(
			(row) => row.custom_upd_sell_price && flt(row.custom_new_sell_rate) > 0
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
})();

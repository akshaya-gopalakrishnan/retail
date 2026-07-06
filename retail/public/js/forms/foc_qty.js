(function () {
	if (!window.frappe?.ui?.form) return;

	const itemDoctypes = [
		"Purchase Order Item",
		"Purchase Receipt Item",
		"Purchase Invoice Item",
		"Sales Order Item",
		"Delivery Note Item",
		"Sales Invoice Item",
		"POS Invoice Item",
		"Stock Entry Detail",
	];

	itemDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			qty(frm, cdt, cdn) {
				updateFocQty(frm, cdt, cdn);
			},
			custom_foc_qty(frm, cdt, cdn) {
				updateFocQty(frm, cdt, cdn);
			},
			conversion_factor(frm, cdt, cdn) {
				updateFocQty(frm, cdt, cdn);
			},
		});
	});

	frappe.ui.form.on("Purchase Order Item", {
		item_code(frm, cdt, cdn) {
			syncPurchaseVatRates(frm, cdt, cdn, "rate");
		},
		rate(frm, cdt, cdn) {
			syncPurchaseVatRates(frm, cdt, cdn, "rate");
		},
		custom_rate_exclusive_vat(frm, cdt, cdn) {
			syncPurchaseVatRates(frm, cdt, cdn, "exclusive");
		},
		custom_rate_including_vat(frm, cdt, cdn) {
			syncPurchaseVatRates(frm, cdt, cdn, "inclusive");
		},
	});

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

	async function syncPurchaseVatRates(frm, cdt, cdn, source) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.__retail_vat_syncing || !row.item_code) return;
		if (row.custom_rate_exclusive_vat === undefined || row.custom_rate_including_vat === undefined) return;

		row.__retail_vat_syncing = true;
		try {
			const vatRate = await getPurchaseVatRate(row.item_code);
			const factor = 1 + (flt(vatRate) / 100);
			const precision = cint(frappe.meta.get_docfield(cdt, "rate", cdn)?.precision) || 2;
			const values = {};
			let exclusiveRate = flt(row.custom_rate_exclusive_vat);
			let inclusiveRate = flt(row.custom_rate_including_vat);

			if (source === "inclusive") {
				inclusiveRate = flt(row.custom_rate_including_vat);
				exclusiveRate = factor ? inclusiveRate / factor : inclusiveRate;
				values.custom_rate_exclusive_vat = flt(exclusiveRate, precision);
				values.rate = values.custom_rate_exclusive_vat;
			} else {
				exclusiveRate = source === "rate" ? flt(row.rate) : flt(row.custom_rate_exclusive_vat);
				if (source === "rate" && !exclusiveRate) return;
				values.custom_rate_exclusive_vat = flt(exclusiveRate, precision);
				values.custom_rate_including_vat = flt(exclusiveRate * factor, precision);
				values.rate = values.custom_rate_exclusive_vat;
			}

			await frappe.model.set_value(cdt, cdn, values);
			frm.refresh_field("items");
		} finally {
			if (row) row.__retail_vat_syncing = false;
		}
	}

	async function getPurchaseVatRate(itemCode) {
		const response = await frappe.call({
			method: "retail.domains.purchase.order.get_purchase_item_vat_rate",
			args: { item_code: itemCode },
		});
		return flt(response.message);
	}
})();

/* All Item Master form behaviour lives here: pricing, VAT and barcode cleanup. */
(function () {
	if (!window.frappe?.ui?.form) return;

	const vatPriceFields = {
		sales: {
			template: "custom_tax", entry: "custom_sales_rate_entry",
			inclusive: "custom_sales_rate_includes_vat", net: "custom_sales_net_rate",
			vat: "custom_sales_vat_amount", gross: "custom_sales_gross_rate", base: "standard_rate",
		},
		purchase: {
			template: "custom_purchase_tax_template", entry: "custom_purchase_rate_entry",
			inclusive: "custom_purchase_rate_includes_vat", net: "custom_purchase_net_rate",
			vat: "custom_purchase_vat_amount", gross: "custom_purchase_gross_rate",
			base: "custom_default_purchase_rate",
		},
	};

	frappe.ui.form.on("Item", {
		refresh(frm) {
			setOpeningAveragePurchaseRate(frm, false);
			refreshVatPrices(frm);
		},
		last_purchase_rate(frm) {
			setOpeningAveragePurchaseRate(frm, true);
		},
		custom_default_purchase_rate(frm) {
			setOpeningAveragePurchaseRate(frm, true);
		},
		custom_tax(frm) { refreshVatPrices(frm, "sales"); },
		custom_purchase_tax_template(frm) { refreshVatPrices(frm, "purchase"); },
		custom_sales_rate_entry(frm) { refreshVatPrices(frm, "sales"); },
		custom_sales_rate_includes_vat(frm) { refreshVatPrices(frm, "sales"); },
		custom_purchase_rate_entry(frm) { refreshVatPrices(frm, "purchase"); },
		custom_purchase_rate_includes_vat(frm) { refreshVatPrices(frm, "purchase"); },
		validate(frm) { removeEmptyBarcodeRows(frm); },
		before_save(frm) { removeEmptyBarcodeRows(frm); },
	});

	function setOpeningAveragePurchaseRate(frm, overwrite) {
		if (!frm.is_new() || (!overwrite && frm.doc.custom_average_purchase_rate)) return;
		frm.set_value("custom_average_purchase_rate", frm.doc.custom_default_purchase_rate || frm.doc.last_purchase_rate || 0);
	}

	function refreshVatPrices(frm, direction) {
		(direction ? [direction] : ["sales", "purchase"]).forEach((side) => calculateVatPrice(frm, side));
	}

	function calculateVatPrice(frm, direction) {
		const fields = vatPriceFields[direction];
		const entry = frm.doc[fields.entry];
		if (entry === undefined || entry === null || entry === "") return;

		frappe.call({
			method: "retail.domains.item.vat_pricing.get_item_tax_rate",
			args: { template: frm.doc[fields.template] },
			callback: ({ message }) => {
				const rate = flt(message || 0);
				const entered = flt(entry);
				const inclusive = cint(frm.doc[fields.inclusive]);
				const net = inclusive && rate ? entered / (1 + rate / 100) : entered;
				const vat = inclusive ? entered - net : net * rate / 100;
				const gross = inclusive ? entered : net + vat;
				frappe.model.set_value("Item", frm.doc.name, {
					[fields.base]: flt(net, 2), [fields.net]: flt(net, 2),
					[fields.vat]: flt(vat, 2), [fields.gross]: flt(gross, 2),
				});
			},
		});
	}

	function removeEmptyBarcodeRows(frm) {
		if (!Array.isArray(frm.doc.barcodes)) return;
		let removed = false;
		for (let index = frm.doc.barcodes.length - 1; index >= 0; index--) {
			const row = frm.doc.barcodes[index];
			if (row.barcode) continue;
			if (row.doctype && row.name) frappe.model.clear_doc(row.doctype, row.name);
			frm.doc.barcodes.splice(index, 1);
			removed = true;
		}
		if (removed) frm.refresh_field("barcodes");
	}
})();

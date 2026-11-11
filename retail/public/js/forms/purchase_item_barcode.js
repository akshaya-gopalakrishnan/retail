// Display the row's scanned/selected barcode; use the Item master only as a fallback.
(() => {
	async function refreshBarcodes(frm) {
		const generation = frm.__retail_barcode_generation = (frm.__retail_barcode_generation || 0) + 1;
		const codes = [...new Set((frm.doc.items || []).map(row => row.item_code).filter(Boolean))];
		if (!codes.length) return;
		const entry = frm.__quick_receipt;
		const cached = entry?.dialog.$wrapper.is(":visible") ? entry.items : new Map();
		if (frm.__retail_purchase_action && window.retail?.transaction_items?.preparedPurchaseItem) {
			const prepared = await Promise.all(codes.filter(code => !cached.has(code)).map(code =>
				window.retail.transaction_items.preparedPurchaseItem(frm, code)));
			if (generation !== frm.__retail_barcode_generation) return;
			for (const item of prepared) {
				if (item && Object.hasOwn(item, "custom_barcode")) cached.set(item.name, item);
			}
		}
		const missing = codes.filter(code => !cached.has(code));
		const items = missing.length ? await frappe.db.get_list("Item", {
			fields: ["name", "custom_barcode"], filters: { name: ["in", missing] }, limit: missing.length,
		}) : [];
		if (generation !== frm.__retail_barcode_generation) return;
		const barcodes = new Map(items.map(item => [item.name, item.custom_barcode || ""]));
		for (const code of codes) if (cached.has(code)) barcodes.set(code, cached.get(code).custom_barcode || "");
		for (const row of frm.doc.items || []) {
			if (row.barcode || barcodes.has(row.item_code)) {
				row.custom_item_barcode = row.barcode || barcodes.get(row.item_code);
			}
		}
		frm.refresh_field("items");
	}
	for (const parent of ["Purchase Invoice", "Purchase Receipt"]) {
		frappe.ui.form.on(parent, { refresh: refreshBarcodes });
		frappe.ui.form.on(`${parent} Item`, { item_code: refreshBarcodes, barcode: refreshBarcodes });
	}
})();

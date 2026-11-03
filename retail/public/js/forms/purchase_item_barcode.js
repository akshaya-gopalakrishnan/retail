// Also display master barcodes on existing rows without saving historical documents.
(() => {
	async function refreshBarcodes(frm) {
		const generation = frm.__retail_barcode_generation = (frm.__retail_barcode_generation || 0) + 1;
		const codes = [...new Set((frm.doc.items || []).map(row => row.item_code).filter(Boolean))];
		if (!codes.length) return;
		const items = await frappe.db.get_list("Item", {
			fields: ["name", "custom_barcode"], filters: { name: ["in", codes] }, limit: codes.length,
		});
		if (generation !== frm.__retail_barcode_generation) return;
		const barcodes = new Map(items.map(item => [item.name, item.custom_barcode || ""]));
		for (const row of frm.doc.items || []) {
			if (barcodes.has(row.item_code)) row.custom_item_barcode = barcodes.get(row.item_code);
		}
		frm.refresh_field("items");
	}
	for (const parent of ["Purchase Invoice", "Purchase Receipt"]) {
		frappe.ui.form.on(parent, { refresh: refreshBarcodes });
		frappe.ui.form.on(`${parent} Item`, { item_code: refreshBarcodes });
	}
})();

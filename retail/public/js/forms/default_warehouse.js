// Offer the Stock Settings warehouse once; subsequent clearing is a user choice.
(() => {
	const is_invoice = frm => ["Sales Invoice", "Purchase Invoice"].includes(frm.doctype);
	async function apply_default(frm) {
		if (Number(frm.doc.docstatus) !== 0 || frm.doc.set_warehouse ||
			(is_invoice(frm) && !Number(frm.doc.update_stock)) ||
			!frm.doc.company || frm.__retail_warehouse_attempted) return;
		frm.__retail_warehouse_attempted = true;
		const doc = frm.doc;
		const company = doc.company;
		const revision = frm.__retail_warehouse_revision || 0;
		const warehouse = await frappe.db.get_single_value("Stock Settings", "default_warehouse");
		if (!warehouse) return;
		const result = await frappe.db.get_value("Warehouse", warehouse, ["company", "is_group", "disabled"]);
		const target = result.message;
		if (frm.doc !== doc || doc.company !== company || Number(doc.docstatus) !== 0 ||
			doc.set_warehouse || revision !== (frm.__retail_warehouse_revision || 0) ||
			(is_invoice(frm) && !Number(doc.update_stock)) ||
			!target || target.company !== company || Number(target.is_group) || Number(target.disabled)) return;
		await frm.set_value("set_warehouse", warehouse);
	}

	for (const doctype of ["Sales Order", "Delivery Note", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Sales Invoice"]) {
		frappe.ui.form.on(doctype, {
			onload(frm) { if (frm.is_new()) return apply_default(frm); },
			company(frm) { if (frm.is_new()) return apply_default(frm); },
			update_stock(frm) { if (is_invoice(frm)) return apply_default(frm); },
			set_warehouse(frm) {
				frm.__retail_warehouse_revision = (frm.__retail_warehouse_revision || 0) + 1;
			},
		});
	}
})();

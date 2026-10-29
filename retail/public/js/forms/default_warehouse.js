// Offer the Stock Settings warehouse without consuming an interrupted attempt.
(() => {
	const is_invoice = frm => ["Sales Invoice", "Purchase Invoice"].includes(frm.doctype);
	function state_for(frm) {
		let state = frm.__retail_warehouse_state;
		if (!state || state.doc !== frm.doc || state.company !== frm.doc.company) {
			state = frm.__retail_warehouse_state = {
				doc: frm.doc, company: frm.doc.company, revision: 0,
				pending: false, attempted: Boolean(frm.doc.set_warehouse),
			};
			frm.__retail_warehouse_attempted = state.attempted;
		}
		return state;
	}
	function bind_user_choice(frm) {
		const input = frm.fields_dict.set_warehouse?.$input;
		input?.off("input.retailDefaultWarehouse").on("input.retailDefaultWarehouse", event => {
			if (!event.originalEvent) return;
			const state = state_for(frm);
			state.attempted = frm.__retail_warehouse_attempted = true;
			state.revision++;
		});
	}
	async function apply_default(frm) {
		const state = state_for(frm);
		if (Number(frm.doc.docstatus) !== 0 || frm.doc.set_warehouse ||
			(is_invoice(frm) && !Number(frm.doc.update_stock)) ||
			!frm.doc.company || state.attempted || state.pending) return;
		state.pending = true;
		const { doc, company, revision } = state;
		try {
			const warehouse = await frappe.db.get_single_value("Stock Settings", "default_warehouse");
			if (!warehouse) return;
			const result = await frappe.db.get_value("Warehouse", warehouse, ["company", "is_group", "disabled"]);
			const target = result.message;
			if (frm.__retail_warehouse_state !== state || frm.doc !== doc ||
				doc.company !== company || Number(doc.docstatus) !== 0 ||
				doc.set_warehouse || revision !== state.revision || state.attempted ||
				(is_invoice(frm) && !Number(doc.update_stock)) ||
				!target || target.company !== company || Number(target.is_group) || Number(target.disabled)) return;
			await frm.set_value("set_warehouse", warehouse);
			state.attempted = true;
			if (frm.__retail_warehouse_state === state) frm.__retail_warehouse_attempted = true;
		} finally {
			state.pending = false;
		}
	}

	for (const doctype of ["Sales Order", "Delivery Note", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Sales Invoice"]) {
		frappe.ui.form.on(doctype, {
			onload(frm) { if (frm.is_new()) return apply_default(frm); },
			refresh(frm) {
				bind_user_choice(frm);
				if (frm.is_new()) return apply_default(frm);
			},
			company(frm) { if (frm.is_new()) return apply_default(frm); },
			update_stock(frm) { if (is_invoice(frm)) return apply_default(frm); },
			set_warehouse(frm) {
				const state = state_for(frm);
				state.revision++;
				if (frm.doc.set_warehouse) state.attempted = true;
				frm.__retail_warehouse_attempted = state.attempted;
			},
		});
	}
})();

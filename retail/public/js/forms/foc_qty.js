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
		frappe.ui.form.on(doctype.replace(/ Item$/, "").replace("Stock Entry Detail", "Stock Entry"), {
			refresh(frm) {
				if (frm.wrapper && !frm.__retail_foc_render_bound) {
					frm.__retail_foc_render_bound = true;
					$(frm.wrapper).on("grid-row-render.retailFocQty", (_event, row) => {
						if (row.doc && row.grid === frm.fields_dict.items?.grid) {
							// Item details can assign the default qty directly after
							// item_code handlers, without firing another qty event.
							updateFocQty(frm, row.doc.doctype, row.doc.name);
						}
					});
				}
				if (Number(frm.doc.docstatus || 0) !== 0) return;
				for (const row of frm.doc.items || []) updateFocQty(frm, row.doctype, row.name);
			},
		});
		frappe.ui.form.on(doctype, {
			item_code(frm, cdt, cdn) {
				return updateFocQty(frm, cdt, cdn);
			},
			qty(frm, cdt, cdn) {
				return updateFocQty(frm, cdt, cdn);
			},
			custom_foc_qty(frm, cdt, cdn) {
				return updateFocQty(frm, cdt, cdn);
			},
			conversion_factor(frm, cdt, cdn) {
				return updateFocQty(frm, cdt, cdn);
			},
		});
	});

	function updateFocQty(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || Number(frm.doc.docstatus || 0) !== 0 || frm.doc.custom_pos_completed_payload ||
			!frappe.meta.has_field(cdt, "custom_total_stock_qty")) return;

		const totalQty = flt(row.qty) + flt(row.custom_foc_qty);
		if (flt(row.custom_total_stock_qty) === totalQty) return;

		const values = {
			custom_total_stock_qty: totalQty,
		};

		return frappe.model.set_value(cdt, cdn, values);
	}
})();

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

	function updateFocQty(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.custom_total_stock_qty === undefined) return;

		const totalQty = flt(row.qty) + flt(row.custom_foc_qty);
		if (flt(row.custom_total_stock_qty) === totalQty) return;

		const values = {
			custom_total_stock_qty: totalQty,
		};

		frappe.model.set_value(cdt, cdn, values);
		frm.refresh_field("items");
	}
})();

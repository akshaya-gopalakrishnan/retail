(function () {
	if (!window.frappe?.ui?.form) return;

	function normalizeRow(frm, cdt, cdn) {
		if (Number(frm.doc.docstatus || 0) !== 0 || !frm.doc.is_return) return;
		const row = locals[cdt]?.[cdn];
		if (row && flt(row.qty) > 0) {
			// Use the normal qty event so stock quantities, taxes and totals recalculate.
			return frappe.model.set_value(cdt, cdn, "qty", -flt(row.qty));
		}
	}

	async function normalizeItems(frm) {
		for (const row of frm.doc.items || []) {
			await normalizeRow(frm, row.doctype, row.name);
		}
	}

	async function toggleReturn(frm) {
		if (Number(frm.doc.docstatus || 0) !== 0) return;
		if (frm.doc.is_return) return normalizeItems(frm);
		for (const row of frm.doc.items || []) {
			if (flt(row.qty) < 0) {
				await frappe.model.set_value(row.doctype, row.name, "qty", Math.abs(flt(row.qty)));
			}
		}
	}

	const returnDoctypes = [
		"Purchase Invoice", "Purchase Receipt", "Sales Invoice",
		"Delivery Note", "POS Invoice", "Subcontracting Receipt",
	];
	for (const doctype of returnDoctypes) {
		frappe.ui.form.on(doctype, {
			is_return: toggleReturn,
			validate: normalizeItems,
		});
		frappe.ui.form.on(`${doctype} Item`, {
			qty: normalizeRow,
			items_add: normalizeRow,
		});
	}
})();

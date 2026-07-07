(function () {
	if (!window.frappe?.ui?.form) return;

	const itemDoctypes = [
		"Purchase Order Item",
		"Purchase Receipt Item",
		"Purchase Invoice Item",
		"Supplier Quotation Item",
		"Material Request Item",
		"Subcontracting Order Item",
		"Subcontracting Receipt Item",
		"Sales Order Item",
		"Delivery Note Item",
		"Sales Invoice Item",
		"POS Invoice Item",
		"Quotation Item",
		"Opportunity Item",
		"Blanket Order Item",
	];

	itemDoctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			item_code(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
			},
			rate(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "rate");
			},
			qty(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "qty");
			},
			custom_rate_including_vat(frm, cdt, cdn) {
				syncVatRates(frm, cdt, cdn, "inclusive");
			},
		});
	});

	bindEditableGridClose();

	async function syncVatRates(frm, cdt, cdn, source) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.__retail_vat_syncing || !row.item_code) return;
		if (row.custom_rate_including_vat === undefined) return;

		row.__retail_vat_syncing = true;
		try {
			const vatRate = await getVatRate(frm, row.item_code, cdt);
			const factor = 1 + (flt(vatRate) / 100);
			const precision = cint(frappe.meta.get_docfield(cdt, "rate", cdn)?.precision) || 2;
			const amountPrecision = cint(frappe.meta.get_docfield(cdt, "amount", cdn)?.precision) || precision;
			const values = {};
			let inclusiveRate = flt(row.custom_rate_including_vat);

			if (source === "inclusive") {
				const exclusiveRate = factor ? inclusiveRate / factor : inclusiveRate;
				values.rate = flt(exclusiveRate, precision);
			} else {
				const exclusiveRate = flt(row.rate);
				if (exclusiveRate) {
					inclusiveRate = flt(exclusiveRate * factor, precision);
					values.custom_rate_including_vat = inclusiveRate;
				}
			}

			if (row.custom_amount_including_vat !== undefined) {
				values.custom_amount_including_vat = flt(flt(row.qty) * inclusiveRate, amountPrecision);
			}

			if (!Object.keys(values).length) return;
			await frappe.model.set_value(cdt, cdn, values);
		} finally {
			if (row) row.__retail_vat_syncing = false;
		}
	}

	async function getVatRate(frm, itemCode, childDoctype) {
		const parentDoc = frm?.doc || {};
		const response = await frappe.call({
			method: "retail.domains.purchase.order.get_transaction_item_vat_rate",
			args: {
				item_code: itemCode,
				child_doctype: childDoctype,
				parent_doctype: parentDoc.doctype,
				transaction_type: parentDoc.transaction_type,
			},
		});
		return flt(response.message);
	}

	function bindEditableGridClose() {
		if (window.__retail_grid_close_bound) return;
		window.__retail_grid_close_bound = true;

		document.addEventListener(
			"keydown",
			(event) => {
				if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) {
					return;
				}
				const row = frappe.ui.form.editable_row;
				if (!row || !row.wrapper?.get(0)?.contains(event.target)) return;
				if (isAutocompleteOpen(event.target)) return;

				setTimeout(() => closeEditableRow(row), 0);
			},
			true
		);

		document.addEventListener(
			"mousedown",
			(event) => {
				const row = frappe.ui.form.editable_row;
				if (!row) return;

				const target = event.target;
				if (row.wrapper?.get(0)?.contains(target)) return;
				if (target.closest(".awesomplete, .modal, .datepicker, .flatpickr-calendar")) return;

				closeEditableRow(row);
			},
			true
		);
	}

	function closeEditableRow(row) {
		if (!row) return;
		if (row.doc?.__retail_vat_syncing) {
			setTimeout(() => closeEditableRow(row), 50);
			return;
		}
		row.toggle_editable_row(false);
	}

	function isAutocompleteOpen(target) {
		const wrapper = target.closest(".awesomplete");
		if (!wrapper) return false;
		const list = wrapper.querySelector("ul");
		return Boolean(list && list.children.length && !list.hidden);
	}
})();

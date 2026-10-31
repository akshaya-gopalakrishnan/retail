// Settlement rows share the native payment grid, but never enter doc.payments.
(() => {
	const selector = ".retail-credit-payment-row";
	function render(frm) {
		const grid = frm.fields_dict.payments?.grid;
		if (!grid?.header_row?.row) return;
		grid.wrapper.find(selector).remove();
		const settlements = frm.doc.__onload?.retail_payment_settlements || [];
		if (!settlements.length) return;
		const parent = grid.wrapper.find(".grid-body .rows");
		settlements.forEach((settlement, index) => {
			// Clone current column widths/order so personal grid choices are retained.
			const row = grid.header_row.row.clone(false).removeClass("editable-row");
			row.children().each(function () {
				const cell = $(this), fieldname = cell.attr("data-fieldname");
				cell.empty();
				if (fieldname === "mode_of_payment") {
					cell.append($("<div class='static-area'></div>").text(__(settlement.mode_of_payment)));
				} else if (fieldname === "amount" || fieldname === "base_amount") {
					const value = fieldname === "base_amount"
						? settlement.amount * (frm.doc.conversion_rate || 1) : settlement.amount;
					cell.append($("<div class='static-area'></div>").html(frappe.format(value, {
						fieldtype: "Currency", options: fieldname === "base_amount" ? "company_currency" : "currency",
					}, null, frm.doc)));
				} else if (fieldname === "reference_no") {
					cell.append($("<div class='static-area'></div>").text(settlement.reference_no || ""));
				} else if (cell.hasClass("row-index")) {
					cell.text((frm.doc.payments || []).length + index + 1);
				}
			});
			$("<div class='grid-row retail-credit-payment-row'></div>")
				.attr("title", [settlement.reference_no, __(settlement.status || "")].filter(Boolean).join(" · "))
				.append(row).appendTo(parent);
		});
		grid.wrapper.find(".grid-empty").addClass("hidden");
		// Core hides submitted empty tables; settlement-only invoices still have rows.
		const field = frm.fields_dict.payments;
		if (frappe.perm.get_field_display_status(field.df, frm.doc, frm.perm) !== "None") {
			const was_hidden = field.$wrapper.hasClass("hide-control");
			field.$wrapper.removeClass("hide-control");
			const section = frm.fields_dict.payments_section;
			section?.wrapper.removeClass("empty-section hide-control");
			if (was_hidden) section?.collapse(false);
		}
	}
	function refresh(frm) {
		const grid = frm.fields_dict.payments?.grid;
		if (!grid) return;
		// Returns/accounting invoices can have is_pos=0 and still own settlements.
		for (const fieldname of ["payments_section", "payments"]) {
			const field = frm.fields_dict[fieldname];
			if (!field || field.df.retail_settlement_dependency) continue;
			field.df.retail_settlement_dependency = true;
			const original = field.df.depends_on;
			const condition = original?.startsWith("eval:") ? original.slice(5)
				: original ? `doc.${original}` : "true";
			frm.set_df_property(fieldname, "depends_on", `eval:(${condition}) || (doc.__onload && doc.__onload.retail_payment_settlements && doc.__onload.retail_payment_settlements.length)`);
			if (fieldname === "payments_section" && field.df.collapsible_depends_on) {
				const collapse = field.df.collapsible_depends_on;
				const expression = collapse.startsWith("eval:") ? collapse.slice(5) : `doc.${collapse}`;
				frm.set_df_property(fieldname, "collapsible_depends_on", `eval:(${expression}) || (doc.__onload && doc.__onload.retail_payment_settlements && doc.__onload.retail_payment_settlements.length)`);
			}
		}
		grid.wrapper.off("change.retail_credit_payments").on("change.retail_credit_payments", () => render(frm));
		render(frm);
	}
	for (const doctype of ["Sales Invoice", "POS Invoice"]) {
		frappe.ui.form.on(doctype, { refresh });
	}
})();

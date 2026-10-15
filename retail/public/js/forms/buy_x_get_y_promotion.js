(function () {
	const fields = ["item", "item_group", "brand"];
	const targetFor = (frm, row) => row.add_to === "Free Item" ? "item" :
		({ ITEM: "item", CATEGORY: "item_group", BRAND: "brand" }[frm.doc.promotion_scope || "ITEM"]);

	function updateColumns(frm) {
		const target = { ITEM: "item", CATEGORY: "item_group", BRAND: "brand" }[frm.doc.promotion_scope || "ITEM"];
		for (const field of fields) {
			frm.fields_dict.products.grid.update_docfield_property(field, "hidden", field !== target ? 1 : 0);
		}
		frm.fields_dict.products.grid.reset_grid();
	}

	function updateRow(frm, row, clear = false) {
		const target = targetFor(frm, row);
		if (clear) {
			for (const field of fields) row[field] = "";
			row.uom = "";
			frm.dirty();
		}
		const gridRow = frm.fields_dict.products.grid.grid_rows_by_docname[row.name];
		if (!gridRow) return;
		for (const field of fields) {
			gridRow.toggle_display(field, field === target);
			gridRow.toggle_editable(field, field === target);
		}
	}

	frappe.ui.form.on("Buy X Get Y Promotion", {
		refresh(frm) {
			updateColumns(frm);
			$(frm.wrapper).off("grid-row-render.buy-scope").on("grid-row-render.buy-scope", (event, row) => {
				if (row.grid.df.fieldname === "products") updateRow(frm, row.doc);
			});
			(frm.doc.products || []).forEach(row => updateRow(frm, row));
		},
		promotion_scope(frm) {
			(frm.doc.products || []).filter(row => row.add_to !== "Free Item").forEach(row => updateRow(frm, row, true));
			updateColumns(frm);
			frm.refresh_field("products");
		},
	});
	frappe.ui.form.on("Buy X Get Y Item", {
		add_to(frm, cdt, cdn) {
			updateRow(frm, locals[cdt][cdn], true);
			updateColumns(frm);
			frm.refresh_field("products");
		},
		form_render(frm, cdt, cdn) { updateRow(frm, locals[cdt][cdn]); },
		products_add(frm, cdt, cdn) { updateColumns(frm); updateRow(frm, locals[cdt][cdn]); },
		products_remove(frm) { updateColumns(frm); },
	});
})();

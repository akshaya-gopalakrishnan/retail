(function () {
	const fields = ["item", "item_group", "brand"];
	const targetFor = (frm, row) => row.add_to === "Free Item" ? "item" :
		({ ITEM: "item", CATEGORY: "item_group", BRAND: "brand" }[frm.doc.promotion_scope || "ITEM"]);

	function updateColumns(frm) {
		const target = { ITEM: "item", CATEGORY: "item_group", BRAND: "brand" }[frm.doc.promotion_scope || "ITEM"];
		for (const field of fields) {
			// Get rows always select concrete Items, including Brand/Category promotions.
			frm.fields_dict.products.grid.update_docfield_property(field, "hidden", field === "item" || field === target ? 0 : 1);
		}
		frm.fields_dict.products.grid.reset_grid();
	}

	function updateRow(frm, row, clear = false, renderedRow = null) {
		if (clear) {
			for (const field of fields) row[field] = "";
			row.uom = "";
			frm.dirty();
		}
		const target = targetFor(frm, row);
		const gridRow = renderedRow || frm.fields_dict.products.grid.grid_rows_by_docname[row.name];
		if (!gridRow) return;
		const otherBuy = (frm.doc.products || []).some(other => other.name !== row.name && other.add_to === "Buy Item");
		const options = otherBuy && row.add_to !== "Buy Item" ? "Free Item" : "Buy Item\nFree Item";
		const addTo = gridRow.docfields.find(field => field.fieldname === "add_to");
		if (addTo) addTo.options = options;
		const column = gridRow.columns.add_to;
		if (column) column.df = { ...column.df, options };
		gridRow.set_field_property("add_to", "options", options);
		for (const field of fields) {
			gridRow.toggle_display(field, field === target);
			gridRow.toggle_editable(field, field === target);
		}
	}

	frappe.ui.form.on("Buy X Get Y Promotion", {
		refresh(frm) {
			$(frm.wrapper).addClass("buy-get-promotion-form");
			if (!$(frm.wrapper).find("style[data-buy-get-dropdown]").length) {
				$("<style data-buy-get-dropdown>").text(`
					.buy-get-promotion-form [data-fieldname="products"] .awesomplete > [role="listbox"] {
						top: auto !important;
						bottom: calc(100% + 4px) !important;
						max-height: min(40vh, 240px);
						overflow-y: auto;
						margin: 0;
					}
				`).appendTo(frm.wrapper);
			}
			updateColumns(frm);
			$(frm.wrapper).off("grid-row-render.buy-scope").on("grid-row-render.buy-scope", (event, row) => {
				if (row.grid.df.fieldname === "products") updateRow(frm, row.doc, false, row);
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
		async item(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			const item = row.item;
			const previousUom = row.uom;
			if (row.add_to === "Free Item" && row.item && (row.item_group || row.brand)) {
				await frappe.model.set_value(cdt, cdn, { item_group: "", brand: "" });
			}
			if (!item) return frappe.model.set_value(cdt, cdn, "uom", "");
			const result = await frappe.db.get_value("Item", item, "stock_uom");
			// A slow lookup must not replace a newer Item or a manually changed UOM.
			if (locals[cdt]?.[cdn] === row && row.item === item && row.uom === previousUom) {
				return frappe.model.set_value(cdt, cdn, "uom", result.message?.stock_uom || "");
			}
		},
		add_to(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			if (row.add_to === "Buy Item" && (frm.doc.products || []).some(other => other.name !== cdn && other.add_to === "Buy Item")) {
				frappe.msgprint(__("Only one Buy Item row is allowed. Add the other products as Free Items."));
				return frappe.model.set_value(cdt, cdn, "add_to", "Free Item");
			}
			updateRow(frm, locals[cdt][cdn], true);
			updateColumns(frm);
			frm.refresh_field("products");
		},
		form_render(frm, cdt, cdn) { updateRow(frm, locals[cdt][cdn]); },
		products_add(frm, cdt, cdn) {
			if ((frm.doc.products || []).some(row => row.name !== cdn && row.add_to === "Buy Item")) {
				return frappe.model.set_value(cdt, cdn, "add_to", "Free Item");
			}
			updateColumns(frm);
			updateRow(frm, locals[cdt][cdn]);
		},
		products_remove(frm) {
			// Free items apply to the promotion's shared Buy list.
			if (!(frm.doc.products || []).some(row => row.add_to === "Buy Item")) {
				for (const row of [...(frm.doc.products || [])]) {
					if (row.add_to === "Free Item") frappe.model.clear_doc(row.doctype, row.name);
				}
				frm.refresh_field("products");
			}
			updateColumns(frm);
		},
	});
})();

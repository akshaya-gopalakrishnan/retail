(function () {
	const fields = ["item", "item_group", "brand"];
	const groupNo = row => Number(row.group_no || 1);
	const targetFor = (frm, row) => row.add_to === "Free Item" ? "item" :
		({ ITEM: "item", CATEGORY: "item_group", BRAND: "brand" }[frm.doc.promotion_scope || "ITEM"]);

	function resizeNotes(frm) {
		const input = frm.fields_dict.notes?.$input?.[0];
		if (!input || !input.getClientRects().length) return;
		input.style.height = "0px";
		const style = getComputedStyle(input);
		const border = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
		input.style.height = Math.max(32, input.scrollHeight + border) + "px";
	}

	function setupDetails(frm) {
		const section = frm.fields_dict.description.$wrapper.closest(".form-section");
		section.addClass("buy-get-details");
		const columns = [
			["description", "disabled", "company", "warehouse"],
			["active_from", "active_from_time", "active_to", "active_to_time"],
			["promotion_scope", "priority", "notes"],
		];
		columns.forEach((fields, column) => fields.forEach((field, row) => {
			frm.fields_dict[field].$wrapper.css({ "--buy-get-column": column + 1, "--buy-get-row": row + 1 });
		}));
		const input = frm.fields_dict.notes.$input;
		if (!input?.length) return;
		input.attr("rows", 1).css({ "min-height": "32px", "overflow-y": "hidden", resize: "none" });
		input.off("input.buy-get-notes").on("input.buy-get-notes", () => resizeNotes(frm));
		frm._buy_get_notes_observer?.disconnect();
		let width;
		frm._buy_get_notes_observer = new ResizeObserver(entries => {
			const nextWidth = entries[0].contentRect.width;
			if (nextWidth !== width) {
				width = nextWidth;
				requestAnimationFrame(() => resizeNotes(frm));
			}
		});
		frm._buy_get_notes_observer.observe(input[0]);
		requestAnimationFrame(() => resizeNotes(frm));
	}

	function updateColumns(frm) {
		const target = { ITEM: "item", CATEGORY: "item_group", BRAND: "brand" }[frm.doc.promotion_scope || "ITEM"];
		for (const field of fields) {
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
		for (const field of fields) {
			gridRow.toggle_display(field, field === target);
			gridRow.toggle_editable(field, field === target);
		}
	}

	function deleteGroup(frm, number) {
		for (const row of [...(frm.doc.products || [])]) {
			if (groupNo(row) === Number(number)) frappe.model.clear_doc(row.doctype, row.name);
		}
		frm.dirty();
		frm.refresh_field("products");
	}

	frappe.ui.form.on("Buy X Get Y Promotion", {
		refresh(frm) {
			$(frm.wrapper).addClass("buy-get-promotion-form");
			if (!$(frm.wrapper).find("style[data-buy-get-dropdown]").length) {
				$("<style data-buy-get-dropdown>").text(`
					.buy-get-promotion-form .buy-get-details > .section-body {
						display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
						column-gap: 32px; align-items: start; padding-inline: 15px;
					}
					.buy-get-promotion-form .buy-get-details > .section-body > .form-column,
					.buy-get-promotion-form .buy-get-details > .section-body > .form-column > form {
						display: contents;
					}
					.buy-get-promotion-form .buy-get-details .frappe-control {
						grid-column: var(--buy-get-column, auto); grid-row: var(--buy-get-row, auto);
						min-width: 0;
					}
					@media (max-width: 1199px) {
						.buy-get-promotion-form .buy-get-details > .section-body { grid-template-columns: repeat(2, minmax(0, 1fr)); }
						.buy-get-promotion-form .buy-get-details .frappe-control { grid-column: auto; grid-row: auto; }
					}
					@media (max-width: 767px) {
						.buy-get-promotion-form .buy-get-details > .section-body { grid-template-columns: minmax(0, 1fr); }
					}
					.buy-get-promotion-form [data-fieldname="products"] .awesomplete > [role="listbox"] {
						top: auto !important; bottom: calc(100% + 4px) !important;
						max-height: min(40vh, 240px); overflow-y: auto; margin: 0;
					}
				`).appendTo(frm.wrapper);
			}
			setupDetails(frm);
			frm.set_df_property("promotion_scope", "read_only", 1);
			updateColumns(frm);
			$(frm.wrapper).off("grid-row-render.buy-scope").on("grid-row-render.buy-scope", (event, row) => {
				if (row.grid.df.fieldname === "products") updateRow(frm, row.doc, false, row);
			});
			(frm.doc.products || []).forEach(row => updateRow(frm, row));
			frm.add_custom_button(__("Add Group"), () => {
				const number = Math.max(0, ...(frm.doc.products || []).map(groupNo)) + 1;
				for (const add_to of ["Buy Item", "Free Item"]) {
					const qty = 1;
					frm.add_child("products", { group_no: number, add_to, qty });
				}
				frm.refresh_field("products");
			});
			frm.add_custom_button(__("Delete Group"), () => {
				const numbers = [...new Set((frm.doc.products || []).map(groupNo))].sort((a, b) => a - b);
				if (!numbers.length) return;
				frappe.prompt([{fieldname: "group_no", label: __("Group No"), fieldtype: "Select",
					options: numbers.map(String).join("\n"), reqd: 1}], values => deleteGroup(frm, values.group_no),
					__("Delete all Buy and Free rows in a group"), __("Delete Group"));
			});
		},
		notes(frm) { requestAnimationFrame(() => resizeNotes(frm)); },
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
			if (locals[cdt]?.[cdn] === row && row.item === item && row.uom === previousUom) {
				return frappe.model.set_value(cdt, cdn, "uom", result.message?.stock_uom || "");
			}
		},
		add_to(frm, cdt, cdn) {
			updateRow(frm, locals[cdt][cdn], true);
			updateColumns(frm);
			frm.refresh_field("products");
		},
		form_render(frm, cdt, cdn) { updateRow(frm, locals[cdt][cdn]); },
		products_add(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			const previous = (frm.doc.products || []).filter(other => other.name !== cdn).at(-1);
			row.group_no = previous ? groupNo(previous) : 1;
			row.qty = 1;
			updateColumns(frm);
			updateRow(frm, row);
		},
	});
})();

// Use native row fields and server bundle creation; do not change Stock Settings.
(() => {
	const tracking = [["serial_no", "has_serial_no"], ["batch_no", "has_batch_no"]];
	function applicable(frm, row, flag) {
		return Boolean(Number(frm.__retail_purchase_tracking.items.get(row.item_code)?.[flag])) &&
			(frm.doctype !== "Purchase Invoice" || (Number(frm.doc.update_stock) === 1 && !Number(row.is_fixed_asset)));
	}

	function styleRow(frm, row) {
		if (!row.doc || row.grid !== frm.fields_dict.items.grid) return;
		for (const [field, flag] of tracking) {
			const show = applicable(frm, row.doc, flag);
			const properties = { hidden: !show, depends_on: "", read_only_depends_on: "",
				read_only: Boolean(row.grid.fields_map[field]?.read_only || row.doc.serial_and_batch_bundle) };
			const df = row.docfields.find(df => df.fieldname === field);
			if (df) Object.assign(df, properties);
			const column = row.columns?.[field];
			if (!column) continue;
			// Native saved-column metadata is shared across rows. Clone before
			// changing a cell so one item's flags cannot change another's input.
			column.df = { ...column.df, ...properties };
			if (column.field) {
				column.field.df = column.df;
				column.field.refresh();
			}
			const editing = row.row.hasClass("editable-row");
			column.field_area?.toggle(show && editing);
			column.static_area?.toggle(show && !editing);
		}
		if (!row.__retail_tracking_toggle) {
			row.__retail_tracking_toggle = true;
			const toggle = row.toggle_editable_row;
			row.toggle_editable_row = function (...args) {
				const result = toggle.apply(this, args);
				styleRow(frm, this);
				return result;
			};
		}
	}

	async function sync(frm, reload = false) {
		const grid = frm.fields_dict.items?.grid;
		if (!grid) return;
		const state = frm.__retail_purchase_tracking ||= { items: new Map(), generation: 0 };
		if (!state.bound) {
			state.bound = true;
			$(frm.wrapper).on("grid-row-render.retailPurchaseTracking", (_event, row) => styleRow(frm, row));
		}
		if (reload) state.items.clear();
		const generation = ++state.generation;
		const codes = [...new Set((frm.doc.items || []).map(row => row.item_code).filter(Boolean))];
		const missing = codes.filter(code => !state.items.has(code));
		if (missing.length) {
			const items = await frappe.db.get_list("Item", {
				fields: ["name", "has_serial_no", "has_batch_no"],
				filters: { name: ["in", missing] },
				limit: missing.length,
			});
			if (generation !== state.generation) return;
			for (const item of items) state.items.set(item.name, item);
		}
		if (generation !== state.generation) return;
		let visibilityChanged = false;
		for (const [field, flag] of tracking) {
			const hidden = !(frm.doc.items || []).some(row => applicable(frm, row, flag));
			visibilityChanged ||= grid.fields_map[field]?.hidden !== hidden;
			grid.update_docfield_property(field, "depends_on", "");
			grid.update_docfield_property(field, "hidden", hidden);
			grid.update_docfield_property(field, "read_only_depends_on", "");
		}
		// refresh() retains visible_columns and existing row columns. Rebuild on
		// visibility transitions, using the user's saved widths and selection.
		if (visibilityChanged) grid.reset_grid();
		else grid.refresh();
		for (const row of grid.grid_rows || []) styleRow(frm, row);
	}

	for (const doctype of ["Purchase Invoice", "Purchase Receipt"]) {
		frappe.ui.form.on(doctype, {
			refresh: frm => sync(frm, true),
			update_stock: frm => sync(frm),
		});
		frappe.ui.form.on(`${doctype} Item`, {
			item_code: frm => sync(frm),
			items_add: frm => sync(frm),
			items_remove: frm => sync(frm),
		});
	}
})();

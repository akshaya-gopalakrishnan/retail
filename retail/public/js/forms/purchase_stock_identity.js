// Use native row fields and server bundle creation; do not change Stock Settings.
(() => {
	const tracking = [["serial_no", "has_serial_no"], ["batch_no", "has_batch_no"]];
	function bindCreate(frm, row, field, control) {
		const input = control?.$input?.[0];
		if (!input || input.__retail_tracking_create) return;
		input.__retail_tracking_create = true;
		input.setAttribute("title", __("Alt+Enter: create batch / serial numbers"));
		input.addEventListener("keydown", event => {
			if (event.key !== "Enter" || !event.altKey || event.ctrlKey || event.metaKey || event.repeat ||
				Number(frm.doc.docstatus || 0) !== 0 || frm.doc.is_return || !frm.perm?.[0]?.write ||
				row.serial_and_batch_bundle || control.df.read_only) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			createTracking(frm, row, field, control);
		}, true);
	}

	function createTracking(frm, row, field, control) {
		const itemCode = row.item_code;
		if (!itemCode) return;
		const current = () => Number(frm.doc.docstatus || 0) === 0 && row.item_code === itemCode &&
			(frm.doc.items || []).includes(row) && !row.serial_and_batch_bundle;
		const fill = async values => {
			await frappe.model.set_value(row.doctype, row.name, values);
			control.set_input?.(row[field] || "");
		};
		if (field === "batch_no") {
			if (!frappe.model.can_create("Batch")) return;
			return frappe.ui.form.make_quick_entry("Batch", batch => {
				if (current()) return fill({batch_no: batch.name, use_serial_batch_fields: 1});
			}, dialog => dialog.set_value("item", itemCode), undefined, true);
		}
		const count = Number(row.qty || 0) * Number(row.conversion_factor || 1);
		if (!Number.isInteger(count) || count < 1) {
			frappe.msgprint(__("Enter a positive whole stock quantity before generating serial numbers."));
			return;
		}
		// Fill the native field; ERPNext creates/validates the Serial No masters
		// through its normal receipt workflow, including separate FOC rows.
		const dialog = new frappe.ui.Dialog({title: __("Create Serial Numbers"), fields: [
			{fieldname: "quantity", fieldtype: "Int", label: __("Serial Numbers to Generate"), default: count, read_only: 1},
			{fieldname: "first_serial_no", fieldtype: "Data", label: __("First Serial No"), reqd: 1,
				description: __("For example, SN-0001 generates SN-0001, SN-0002, and so on for this row's stock quantity.")},
		], primary_action_label: __("Fill Serial Numbers"), primary_action: async values => {
			if (!current()) return;
			if (count !== Number(row.qty || 0) * Number(row.conversion_factor || 1)) {
				frappe.throw(__("Quantity changed. Open serial number generation again."));
			}
			const first = values.first_serial_no.trim();
			const match = first.match(/^(.*?)(\d+)$/);
			if (!match && count !== 1) frappe.throw(__("The first serial number must end with a number."));
			const serials = Array.from({length: count}, (_, index) => match
				? match[1] + String(BigInt(match[2]) + BigInt(index)).padStart(match[2].length, "0") : first);
			const others = new Set((frm.doc.items || []).filter(other => other !== row)
				.flatMap(other => String(other.serial_no || "").split(/\s*\n\s*/)));
			if (serials.some(serial => others.has(serial))) frappe.throw(__("A generated serial number is already in another receipt row."));
			const existing = await frappe.db.get_list("Serial No", {fields: ["name"], filters: {name: ["in", serials]}, limit: count});
			if (existing.length) frappe.throw(__("Serial number {0} already exists. Choose another starting number.", [existing[0].name]));
			if (!current()) return;
			if (count !== Number(row.qty || 0) * Number(row.conversion_factor || 1)) {
				frappe.throw(__("Quantity changed. Open serial number generation again."));
			}
			await fill({serial_no: serials.join("\n"), use_serial_batch_fields: 1});
			dialog.hide();
		}});
		dialog.show();
		return dialog;
	}
	window.retail = window.retail || {};
	window.retail.purchase_tracking = { bindCreate };
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
				if (show) bindCreate(frm, row.doc, field, column.field);
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
		grid.retail_purchase_tracking = true;
		const state = frm.__retail_purchase_tracking ||= { items: new Map(), generation: 0 };
		if (!state.bound) {
			state.bound = true;
			$(frm.wrapper).on("grid-row-render.retailPurchaseTracking", (_event, row) => styleRow(frm, row));
		}
		if (reload) state.items.clear();
		const generation = ++state.generation;
		const codes = [...new Set((frm.doc.items || []).map(row => row.item_code).filter(Boolean))];
		// Item loading already fetched permission-filtered metadata. Reuse only
		// the required fields from that action; ordinary refresh keeps its read.
		if (frm.__retail_purchase_action && window.retail?.transaction_items?.preparedPurchaseItem) {
			const prepared = await Promise.all(codes.filter(code => !state.items.has(code)).map(code =>
				window.retail.transaction_items.preparedPurchaseItem(frm, code)));
			if (generation !== state.generation) return;
			for (const item of prepared) {
				if (item && Object.hasOwn(item, "has_serial_no") && Object.hasOwn(item, "has_batch_no")) state.items.set(item.name, item);
			}
		}
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
		// New-style item_code handlers finish before ERPNext's controller handler.
		// Select its native inline-entry path before it decides to open the popup.
		// Existing bundles retain their current allocation workflow.
		if (Number(frm.doc.docstatus || 0) === 0) {
			for (const row of frm.doc.items || []) {
				if (!row.serial_and_batch_bundle && tracking.some(([, flag]) => applicable(frm, row, flag))) {
					row.use_serial_batch_fields = 1;
				}
			}
		}
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

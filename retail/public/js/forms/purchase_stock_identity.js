// Use native row fields and server bundle creation; do not change Stock Settings.
(() => {
	const tracking = [["serial_no", "has_serial_no"], ["batch_no", "has_batch_no"]];
	async function withBatchPriceReads(frm, update) {
		const controller = frm.cscript;
		const original = controller?.batch_no;
		if (typeof original !== "function") return update();
		const reads = new Map();
		controller.batch_no = function (...args) {
			const call = frappe.call;
			const pending = [];
			// Capture only the native handler's synchronous price read. Restore the
			// dispatcher before awaiting anything; unrelated calls remain native.
			frappe.call = function (request, ...rest) {
				if (request?.method !== "erpnext.stock.get_item_details.get_batch_based_item_price") {
					return call.call(this, request, ...rest);
				}
				const params = request.args?.params;
				if (!params || typeof params !== "object") return call.call(this, request, ...rest);
				// This read uses item/batch/UOM/party/date/price context, never child
				// record IDs. Keep every other argument in its per-dialog cache key.
				const key = JSON.stringify({...request.args, params: {...params,
					items: params.items?.map(({name, child_docname, ...item}) => item)}});
				if (!reads.has(key)) {
					reads.set(key, Promise.resolve(call.call(this, {...request, callback: undefined})));
				}
				const result = reads.get(key).then(response => request.callback?.(response));
				pending.push(result);
				return result;
			};
			let result;
			try { result = original.apply(this, args); }
			finally { frappe.call = call; }
			return Promise.all([result, ...pending]);
		};
		try { return await update(); }
		finally { controller.batch_no = original; }
	}
	function bindCreate(frm, row, field, control) {
		// Sales use existing serials/batches; receipt creation shortcuts do not apply.
		if (frm.doctype === "Sales Invoice") return;
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
			(!["Purchase Invoice", "Sales Invoice"].includes(frm.doctype) ||
				(Number(frm.doc.update_stock) === 1 && !Number(row.is_fixed_asset)));
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

	async function sync(frm, reload = false, cdn) {
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
		if (!reload && frm.__retail_purchase_action && window.retail?.transaction_items?.preparedPurchaseItem) {
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
				fields: ["name", "has_serial_no", "has_batch_no", "create_new_batch"],
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
			visibilityChanged ||= grid.fields_map[field]?.hidden == null || Boolean(grid.fields_map[field].hidden) !== hidden;
			for (const [property, value] of Object.entries({depends_on: "", hidden, read_only_depends_on: ""})) {
				const current = grid.fields_map[field]?.[property];
				const unchanged = property === "hidden" ? current != null && Boolean(current) === value : current === value;
				if (!unchanged) grid.update_docfield_property(field, property, value);
			}
		}
		// Rebuild only when a serial or batch column appears or disappears.
		// Restyling every existing row on each added line is what makes entry lag.
		if (visibilityChanged) grid.reset_grid();
		// Pagination leaves holes in grid_rows. Visiting one throws and stops refresh.
		const renderedRows = (grid.grid_rows || []).filter(row => row);
		if (visibilityChanged || reload) {
			for (const row of renderedRows) styleRow(frm, row);
		} else {
			const target = cdn && grid.grid_rows_by_docname?.[cdn];
			if (target) styleRow(frm, target);
			for (const row of renderedRows) {
				if (!row.__retail_tracking_toggle) styleRow(frm, row);
			}
		}
	}

	for (const doctype of ["Purchase Invoice", "Purchase Receipt", "Sales Invoice"]) {
		frappe.ui.form.on(doctype, {
			refresh: frm => sync(frm, true),
			update_stock: frm => sync(frm),
			async before_submit(frm) {
				await sync(frm, true);
				const missing = [];
				for (const row of frm.doc.items || []) {
					if (row.serial_and_batch_bundle) continue;
					for (const [field, flag] of tracking) {
						if (frm.doctype !== "Sales Invoice" && field === "batch_no" && !frm.doc.is_return &&
							Number(frm.__retail_purchase_tracking.items.get(row.item_code)?.create_new_batch)) continue;
						if (applicable(frm, row, flag) && !String(row[field] || "").trim()) {
							missing.push({row, field});
						}
					}
				}
				if (!missing.length) return;
				frappe.validated = false;
				const dialog = new frappe.ui.Dialog({
					title: __("Enter Batch / Serial Numbers"),
					size: "large",
					fields: missing.flatMap(({row, field}, index) => [{
						fieldname: `tracking_${index}`,
						fieldtype: field === "batch_no" ? "Link" : "Small Text",
						options: field === "batch_no" ? "Batch" : undefined,
						label: __("Row {0}: {1} — {2}", [row.idx, row.item_name || row.item_code,
							field === "batch_no" ? __("Batch No") : __("Serial Nos")]),
						reqd: 1,
						get_query: () => ({filters: {item: row.item_code}}),
						get_route_options_for_new_doc: () => ({item: row.item_code}),
						description: field === "serial_no" ? __("Required serial numbers: {0}. Enter one serial number per line.",
							[Math.abs(Number(row.qty || 0) * Number(row.conversion_factor || 1))]) : undefined,
						}, ...(field === "batch_no" && frappe.model.can_create("Batch") ? [{
							fieldname: `create_batch_${index}`, fieldtype: "Button", label: __("Create Batch"),
							click: () => frappe.ui.form.make_quick_entry("Batch", batch => {
								if ((frm.doc.items || []).includes(row)) dialog.set_value(`tracking_${index}`, batch.name);
							}, batchDialog => batchDialog.set_value("item", row.item_code), undefined, true),
						}] : [])]),
					primary_action_label: __("Save Tracking Details"),
					primary_action: async values => {
						// Validate every serial row before changing the invoice. Quantity is
						// in stock UOM, including packing conversion, not the purchase UOM.
						for (const [index, {row, field}] of missing.entries()) {
							if (field !== "serial_no") continue;
							const serials = String(values[`tracking_${index}`] || "").split(/\r?\n/).map(s => s.trim()).filter(Boolean);
							const count = Math.abs(Number(row.qty || 0) * Number(row.conversion_factor || 1));
							if (serials.length !== count || new Set(serials).size !== count) {
								frappe.throw(__("Row {0}: enter exactly {1} unique serial numbers ({2} entered).", [row.idx, count, serials.length]));
							}
							values[`tracking_${index}`] = serials.join("\n");
						}
						dialog.disable_primary_action();
						try {
							if (missing.some(({row}) => !(frm.doc.items || []).includes(row))) return;
							const update = async () => {
								// Native handlers still run in row order, including batch pricing.
								// Paint the final grid once instead of after every tracked row.
								for (const [index, {row, field}] of missing.entries()) {
									await frappe.model.set_value(row.doctype, row.name, {
										[field]: values[`tracking_${index}`], use_serial_batch_fields: 1,
									});
								}
							};
							const batchUpdates = window.retail?.transaction_items?.withTrackingUpdates;
							await withBatchPriceReads(frm, () => batchUpdates ? batchUpdates(frm, update) : update());
							frappe.validated = true;
							// Close only on the native save success callback. Form.save catches
							// rejections internally, so awaiting it alone cannot prove success.
							await frm.save("Save", response => {
								if (response?.exc) return;
								// The save has succeeded; do not keep the completed dialog
								// on screen for Bootstrap's extra closing transition.
								dialog.$wrapper?.removeClass?.("fade");
								dialog.hide();
								frappe.show_alert({message: __("Tracking details saved. Click Submit to confirm the invoice."), indicator: "green"});
							}, undefined, () => dialog.enable_primary_action());
						} finally {
							dialog.enable_primary_action();
						}
					},
				});
				dialog.show();
			},
		});
		frappe.ui.form.on(`${doctype} Item`, {
			item_code(frm, cdt, cdn) { return sync(frm, false, cdn); },
			items_add(frm, cdt, cdn) { return sync(frm, false, cdn); },
			items_remove(frm) { return sync(frm); },
		});
	}
})();

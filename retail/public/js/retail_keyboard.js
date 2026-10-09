/* Shared Desk keyboard navigation: required header fields, editable item cells,
 * and Shift+Enter to the form scanner. Tab and submission remain native.
 * Optional client-script configuration:
 * retail.keyboard.doctypes["My Document"] = { scan_field: "custom_scan" };
 * retail.keyboard.children["My Item"] = { first_field: "item_code", skip: ["rate"] };
 * Either config accepts enabled: false. scan_field: false disables scan detection.
 * For custom async scanners, when_scan_complete(frm) may return their completion promise.
 */
(() => {
	frappe.provide("retail.keyboard");
	const api = retail.keyboard;
	if (api.installed) return;
	api.installed = true;
	api.doctypes ||= {};
	api.children ||= {};
	const scanNames = ["scan_barcode", "barcode", "item_barcode"];
	const native = "textarea,select,button,a,[contenteditable]:not([contenteditable=false]),[role=button]";
	let generation = 0;
	let pending = 0;
	const visible = (el) => !!el && $(el).is(":visible");
	const enabled = (el) => visible(el) && !el.disabled && !el.readOnly &&
		!el.closest('[aria-disabled="true"],.disabled');
	const frozen = () => $("#freeze:not(.grid-form):visible,.freeze:not(.grid-form):visible").length;
	// Air Datepicker keeps closed panels measurable off-screen; only .active is open.
	const blocked = (includeFreeze = true) => window.cur_dialog || (includeFreeze && frozen()) ||
		$(".modal:visible,.dropdown-menu:visible,[role=listbox]:visible,.awesomplete > ul:visible,.datepicker.active:visible").length;
	const current = () => {
		const frm = window.cur_frm;
		return frappe.get_route()[0] === "Form" && visible(frm?.wrapper) ? frm : null;
	};
	const scanField = (frm) => {
		const override = api.doctypes[frm.doctype]?.scan_field;
		return (override === false ? [] : override ? [override] : scanNames)
			.map((name) => frm.fields_dict[name])
			.find((field) => field && !field.df.hidden && !field.df.read_only &&
				!field.grid && enabled(field.$input?.[0]));
	};
	function reveal(input) {
		if (!input?.getBoundingClientRect || !input.scrollIntoView) return;
		// Native nearest scrolling handles the page and nested vertical containers.
		input.scrollIntoView({block: "nearest", inline: "nearest", behavior: "instant"});
		const margin = 12;
		const viewportHeight = window.innerHeight;
		let top = margin;
		const rect = input.getBoundingClientRect();
		// Desk's fixed navbar and sticky page toolbar can cover a natively revealed input.
		for (const bar of Array.from(document.querySelectorAll(".sticky-top, .navbar, .page-head, .form-tabs-list"))
			.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)) {
			const style = getComputedStyle(bar);
			const bounds = bar.getBoundingClientRect();
			if (!["fixed", "sticky"].includes(style.position) || style.visibility === "hidden" ||
				!bounds.height || bounds.bottom <= 0 || bounds.top > top ||
				bounds.right <= rect.left || bounds.left >= rect.right) continue;
			// Reserve the full stack while Desk animates sticky bars on scroll.
			top = Math.max(top + bounds.height, bounds.bottom + margin);
		}
		const dy = rect.top < top ? rect.top - top :
			rect.bottom > viewportHeight - margin ? rect.bottom - viewportHeight + margin : 0;
		if (dy) window.scrollBy({top: dy, left: 0, behavior: "instant"});

		const container = input.closest(".retail-scrollable-grid .form-grid-container");
		const row = input.closest(".data-row");
		if (!container || !row || input.closest(".retail-grid-pinned")) return;
		const bounds = container.getBoundingClientRect();
		let left = Math.max(0, bounds.left) + margin;
		let right = Math.min(window.innerWidth, bounds.right) - margin;
		for (const pinned of row.querySelectorAll(".row-check, .row-index, .retail-grid-pinned")) {
			if (getComputedStyle(pinned).position !== "sticky") continue;
			const pin = pinned.getBoundingClientRect();
			if (getComputedStyle(container).direction === "rtl") right = Math.min(right, pin.left - margin);
			else left = Math.max(left, pin.right + margin);
		}
		const cell = input.getBoundingClientRect();
		const dx = cell.left < left ? cell.left - left : cell.right > right ? cell.right - right : 0;
		if (dx) container.scrollBy({left: dx, top: 0, behavior: "instant"});
	}

	const focus = (field) => {
		const input = field?.$input?.[0];
		if (enabled(input)) { input.focus({preventScroll: true}); input.select?.(); reveal(input); }
	};
	const consume = (event) => { event.preventDefault(); event.stopImmediatePropagation(); };
	let selected = null;
	const expanded = (row) => visible(row.grid_form?.wrapper);
	// Inline controls are lazy: columns exist before make_control creates $input.
	const controls = (row) => {
		const config = api.children[row.doc.doctype] || {};
		const fields = expanded(row)
			? (row.grid_form.fields || Object.values(row.grid_form.fields_dict)).map((field) =>
				({ df: field.df, field, cell: field.$wrapper || field.wrapper }))
			: (row.columns_list || []).map((column) =>
				({ df: column.df, field: column.field, cell: column }));
		return fields.filter(({ df, field, cell }) =>
			!df.hidden && !df.hidden_due_to_dependency && !df.read_only && !df.disabled && !df.is_virtual &&
			!config.skip?.includes(df.fieldname) &&
			!frappe.model.no_value_type?.includes(df.fieldtype) &&
			!['Read Only', 'Table', 'Table MultiSelect'].includes(df.fieldtype) &&
			visible($(cell)[0]) && !field?.$input?.[0]?.disabled && !field?.$input?.[0]?.readOnly &&
			(!field?.get_status || field.get_status() === 'Write')
		);
	};
	$('<style id="retail-keyboard-style">.retail-keyboard-selected{outline:2px solid var(--primary,#2490ef)!important;outline-offset:-2px;background-color:var(--control-bg,#f4f5f6)}</style>').appendTo(document.head);
	const clearSelection = () => {
		$('.retail-keyboard-selected').each(function () {
			const previous = $(this).data('retail-keyboard-tabindex');
			if (previous == null) $(this).removeAttr('tabindex');
			else $(this).attr('tabindex', previous);
		}).removeClass('retail-keyboard-selected');
		selected = null;
	};
	const select = (row, name) => {
		if (!expanded(row)) row.toggle_editable_row(false);
		const entry = controls(row).find(({ df }) => df.fieldname === name);
		if (!entry) { clearSelection(); return; }
		clearSelection();
		selected = { grid: row.grid, name: row.doc.name, fieldname: name };
		$(entry.cell).data('retail-keyboard-tabindex', $(entry.cell).attr('tabindex') ?? null)
			.addClass('retail-keyboard-selected').attr('tabindex', '-1')[0].focus({preventScroll: true});
		reveal($(entry.cell)[0]);
	};
	const edit = (row, name) => {
		clearSelection();
		if (!expanded(row)) {
			if (row.grid.allow_on_grid_editing()) row.activate();
			else {
				row.toggle_view(true);
				// GridRowForm schedules its initial focus after a 500ms animation.
				const token = generation;
				setTimeout(() => {
					if (token === generation && expanded(row) && current() === row.grid.frm) {
						focus(controls(row).find(({ df }) => df.fieldname === name)?.field);
					}
				}, 550);
			}
		}
		focus(controls(row).find(({ df }) => df.fieldname === name)?.field);
	};
	// Refresh can replace GridRow instances; resolve by document identity each time.
	$(document).on('grid-row-render.retailKeyboard', (event, row) => {
		if (selected?.grid !== row.grid || selected.name !== row.doc.name) return;
		const name = selected.fieldname;
		queueMicrotask(() => {
			if (selected?.name === row.doc.name && selected.fieldname === name &&
				(document.activeElement === document.body || document.activeElement.classList.contains('retail-keyboard-selected'))) {
				select(row.grid.grid_rows_by_docname[row.doc.name] || row, name);
			}
		});
	});
	// Manual navigation awaits the actual field commit, with no quiet-period delay.
	// Native scanners still need to outlast their debounced event/server callbacks.
	// Cancel on user activity, navigation, or a prompt requiring user input.
	async function settled(frm, field, token, scan = false) {
		pending++;
		try {
			await Promise.resolve(); // Native Enter handlers run before the optional completion hook.
			if (scan && api.doctypes[frm.doctype]?.when_scan_complete) {
				await api.doctypes[frm.doctype].when_scan_complete(frm);
			}
			if (!scan) {
				for (let elapsed = 0; elapsed < 30000; elapsed += 16) {
					if (token !== generation || current() !== frm || blocked(false)) return false;
					if (!frozen() && !field?.inside_change_event) return true;
					await new Promise((resolve) => setTimeout(resolve, 16));
				}
				return false;
			}
			let quiet = 0;
			for (let elapsed = 0; elapsed < 30000; elapsed += 100) {
				await new Promise((resolve) => setTimeout(resolve, 100));
				if (token !== generation || current() !== frm || blocked(false)) return false;
				quiet = frozen() || frappe.request.ajax_count || field?.inside_change_event ||
					frappe.flags.trigger_from_barcode_scanner ? 0 : quiet + 100;
				if (quiet >= 700) return true;
			}
			return false;
		} finally { pending--; }
	}
	const headerFields = (frm) => (frm.fields || Object.values(frm.fields_dict)).filter((field) =>
		!field.grid && !field.df.hidden && !field.df.hidden_due_to_dependency &&
		!field.df.read_only && !field.df.disabled && !field.df.is_virtual &&
		enabled(field.$input?.[0]) && (!field.get_status || field.get_status() === "Write"));

	async function commit(frm, field, target, token, requireValue = true) {
		const value = field?.get_input_value ? field.get_input_value() : target.value;
		if (requireValue && field?.df.reqd && (value == null || String(value).trim() === "")) {
			frappe.show_alert?.({message: __("Please fill {0}", [__(field.df.label || field.df.fieldname)]), indicator: "orange"});
			focus(field);
			return false;
		}
		try {
			// A debounced change may already be validating an older input value.
			// Wait for that specific control, then commit the latest value ourselves.
			if (field?.inside_change_event && !await settled(frm, field, token)) return false;
			if (field?.parse_validate_and_set_in_model) {
				await field.parse_validate_and_set_in_model(value);
			}
			if (token !== generation || current() !== frm) return false;
			if (field?.df.invalid || requireValue && field?.df.reqd && field?.get_model_value &&
				[field.get_model_value()].some((v) => v == null || v === "")) {
				focus(field);
				return false;
			}
			if (token !== generation || current() !== frm) return false;
			target.blur();
			return await settled(frm, field, token);
		} catch (error) {
			if (token === generation && current() === frm) focus(field);
			console.error(error);
			return false;
		}
	}

	function firstCell(row) {
		const entries = controls(row);
		const preferred = api.children[row.doc.doctype]?.first_field;
		return entries.find(({df}) => df.fieldname === preferred) || entries[0];
	}

	async function focusItems(frm, token) {
		const grid = frm.fields_dict[api.doctypes[frm.doctype]?.items_field || "items"]?.grid;
		if (!grid?.is_editable() || api.children[grid.df.options]?.enabled === false) return;
		let row = grid.grid_rows?.find((row) => row.doc && firstCell(row));
		if (!row && !grid.get_data().length && !grid.cannot_add_rows && !grid.df.cannot_add_rows) {
			const doc = grid.add_new_row(null, null, false);
			if (!doc || !await settled(frm, null, token)) return;
			row = grid.grid_rows_by_docname[doc.name];
		}
		const first = row && firstCell(row);
		if (first) edit(row, first.df.fieldname);
	}

	async function nextCell(frm, row, name, token) {
		const grid = row.grid;
		const live = grid.grid_rows_by_docname[row.doc.name];
		if (!live || !grid.is_editable()) return;
		const entries = controls(live);
		const index = entries.findIndex(({df}) => df.fieldname === name);
		if (index < 0) return;
		if (entries[index + 1]) return edit(live, entries[index + 1].df.fieldname);
		// Defaults such as qty=1 do not make an empty item row a completed row.
		if (!live.doc.item_code && grid.docfields.some((df) => df.fieldname === "item_code")) {
			const first = firstCell(live);
			if (first) edit(live, first.df.fieldname);
			return;
		}
		if (grid.cannot_add_rows || grid.df.cannot_add_rows) return;
		if (expanded(live)) live.toggle_view(false);
		const doc = grid.add_new_row(live.doc.idx + 1, null, false);
		if (!doc || !await settled(frm, null, token)) return;
		// An insertion at a page boundary must reveal the new row.
		if (!grid.grid_rows_by_docname[doc.name] && grid.grid_pagination) {
			const size = grid.grid_pagination.page_length;
			if (size) grid.grid_pagination.go_to_page(Math.ceil(doc.idx / size));
		}
		const added = grid.grid_rows_by_docname[doc.name];
		const first = added && firstCell(added);
		if (first) edit(added, first.df.fieldname);
	}

	// One ordered route through parent controls and every rendered editable table cell.
	function arrowEntries(frm) {
		const headers = new Set(headerFields(frm));
		return (frm.fields || Object.values(frm.fields_dict)).flatMap((field) => {
			const grid = field.grid;
			if (!grid) return headers.has(field) ? [{field}] : [];
			if (field.df.hidden || field.df.hidden_due_to_dependency || !grid.is_editable() ||
				api.children[grid.df.options]?.enabled === false) return [];
			const entries = (grid.grid_rows || []).flatMap((row) => row.doc
				? controls(row).map(({df}) => ({row, name: df.fieldname})) : []);
			if (!entries.length && !grid.get_data().length &&
				field.df.fieldname === (api.doctypes[frm.doctype]?.items_field || "items") &&
				!grid.cannot_add_rows && !grid.df.cannot_add_rows &&
				visible(field.$wrapper?.[0] || field.wrapper)) return [{grid}];
			return entries;
		});
	}

	function entryRect(entry) {
		const element = entry.field?.$input?.[0] || (entry.grid ? $(entry.grid.wrapper)[0] :
			$(controls(entry.row).find(({df}) => df.fieldname === entry.name)?.cell)[0]);
		return element?.getBoundingClientRect?.();
	}

	function arrowDestination(frm, row, name, field, key) {
		const entries = arrowEntries(frm);
		const origin = entries.find((entry) => row
			? entry.row === row && entry.name === name : entry.field === field);
		if (!origin) return;
		const from = entryRect(origin);
		if (!from) return;
		const horizontal = ["ArrowLeft", "ArrowRight"].includes(key);
		const forward = ["ArrowDown", "ArrowRight"].includes(key);
		const center = (rect, axis) => axis === "x" ? (rect.left + rect.right) / 2 : (rect.top + rect.bottom) / 2;
		let best, bestScore = Infinity;
		for (const entry of entries) {
			if (entry === origin) continue;
			const rect = entryRect(entry);
			if (!rect || rect.right <= rect.left || rect.bottom <= rect.top) continue;
			// Stay in the same visual row/column; never wrap horizontally to another row.
			const overlap = horizontal
				? Math.min(from.bottom, rect.bottom) - Math.max(from.top, rect.top)
				: Math.min(from.right, rect.right) - Math.max(from.left, rect.left);
			if (overlap <= 0) continue;
			const delta = center(rect, horizontal ? "x" : "y") - center(from, horizontal ? "x" : "y");
			if (forward ? delta <= 1 : delta >= -1) continue;
			const deviation = Math.abs(center(rect, horizontal ? "y" : "x") - center(from, horizontal ? "y" : "x"));
			const score = Math.abs(delta) + deviation * 0.25;
			if (score < bestScore) { best = entry; bestScore = score; }
		}
		return best;
	}

	async function focusArrowEntry(next, frm, token) {
		if (next.grid) return focusItems(frm, token);
		if (next.row) {
			const live = next.row.grid.grid_rows_by_docname[next.row.doc.name];
			if (live) edit(live, next.name);
		} else focus(next.field);
	}

	// Also cover native Tab navigation. No scroll listener: manual scrolling stays put.
	document.addEventListener("focusin", (event) => {
		const frm = current();
		if (!frm || api.doctypes[frm.doctype]?.enabled === false || window.cur_dialog ||
			!frm.wrapper.contains(event.target)) return;
		queueMicrotask(() => {
			if (document.activeElement === event.target && current() === frm) reveal(event.target);
		});
	}, true);
	document.addEventListener("pointerdown", () => { generation++; clearSelection(); }, true);
	frappe.router.on("change", () => { generation++; clearSelection(); });
	document.addEventListener("keydown", (event) => {
		// Repeated Enter must not cancel the first in-flight commit or create extra rows.
		const repeatedEnter = event.repeat && event.key === "Enter";
		const token = repeatedEnter ? generation : ++generation;
		const frm = current();
		if (!frm || api.doctypes[frm.doctype]?.enabled === false || event.isComposing || event.keyCode === 229) return;
		// Tab (including Shift+Tab), save shortcuts and native controls keep their own handlers.
		if (event.ctrlKey || event.metaKey || event.altKey || event.key === "Tab") return;
		if (event.shiftKey && event.key !== "Enter") return;
		if (!["Enter", "ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Escape"].includes(event.key)) return;
		const target = event.target;
		const arrow = event.key.startsWith("Arrow");
		const returnToScan = event.shiftKey && event.key === "Enter";
		// Shift+Enter is an explicit exit from a field's suggestions, not a selection.
		const blockedHere = returnToScan
			? window.cur_dialog || frozen() || $(".modal:visible").length : blocked();
		if (blockedHere) return;
		if (!returnToScan && (!frm.wrapper.contains(target) ||
			target.closest(arrow ? "button,a,[role=button],[contenteditable]:not([contenteditable=false])" : native))) return;
		if (returnToScan && target !== document.body && !frm.wrapper.contains(target)) return;
		if (repeatedEnter) { consume(event); return; }
		const scan = scanField(frm);
		if (event.key === "Enter" && !event.shiftKey && target === scan?.$input[0]) {
			// The scanner owns Enter and its server calls. Keep focus for repeated scans.
			settled(frm, scan, token, true).then((ok) => ok && focus(scanField(frm))).catch(console.error);
			return;
		}
		const row = $(target).closest(".grid-row").data("grid_row");
		const fields = row?.doc ? controls(row) : [];
		const entry = fields.find(({field, cell}) => field?.$input?.[0] === target ||
			$(cell)[0] === target || $(cell)[0]?.contains(target));
		const field = entry?.field || headerFields(frm).find((field) => field.$input[0] === target);
		if (!returnToScan && row && (api.children[row.doc.doctype]?.enabled === false || !row.grid.is_editable())) return;
		if (returnToScan) {
			if (!scan) return;
			consume(event);
			field?.awesomplete?.close();
			field?.datepicker?.hide();
			(async () => {
				if (field && !await commit(frm, field, target, token, false)) return;
				if (row && expanded(row)) row.toggle_view(false);
				clearSelection();
				focus(scanField(frm));
			})().catch(console.error);
			return;
		}
		if (event.key === "Enter" && target.type === "checkbox" && field && enabled(target)) {
			consume(event);
			// Native click toggles checked and runs Frappe's normal change/model handlers.
			target.click();
			return;
		}
		if (arrow && (entry || field)) {
			const next = arrowDestination(frm, row?.doc ? row : null, entry?.df.fieldname, field, event.key);
			// Even at an edge, arrows must not alter numbers, selections or caret position.
			consume(event);
			if (!next) return;
			(async () => {
				if (field?.$input?.[0] === target && !await commit(frm, field, target, token, false)) return;
				await focusArrowEntry(next, frm, token);
			})().catch(console.error);
			return;
		}
		if (row?.doc && entry) {
			const name = entry.df.fieldname;
			const isInput = entry.field?.$input?.[0] === target;
			if (event.key === "Escape") { consume(event); target.blur(); select(row, name); return; }
			consume(event);
			if (!isInput) return edit(row, name);
			(async () => {
				if (await commit(frm, field, target, token)) await nextCell(frm, row, name, token);
			})().catch(console.error);
			return;
		}
		if (event.key !== "Enter" || !field) return;
		consume(event);
		(async () => {
			if (!await commit(frm, field, target, token)) return;
			const headers = headerFields(frm);
			const index = headers.findIndex((candidate) => candidate.df.fieldname === field.df.fieldname);
			const next = headers.slice(index + 1).find((candidate) => candidate.df.reqd && candidate !== scanField(frm));
			if (next) return focus(next);
			if (scanField(frm)) return focus(scanField(frm));
			await focusItems(frm, token);
		})().catch(console.error);
	}, true);
})();

/* Opt-in horizontal layout for native Frappe child-table grids.
 * Enable another table with retail.scrollable_grid.register(doctype, fieldname, options).
 * No global Grid/GridRow prototype changes; native controls handle edits and validation.
 */
(() => {
	window.retail = window.retail || {};
	if (retail.scrollable_grid) return;
	const SETTINGS = "RetailScrollableGrid";
	const registrations = new Set();

	function setupColumns() {
		if (this.visible_columns?.length) return;
		const own = frappe.get_user_settings(this.frm.doctype, SETTINGS) || {};
		const legacy = frappe.get_user_settings(this.frm.doctype, "GridView") || {};
		let saved = Object.prototype.hasOwnProperty.call(own, this.df.fieldname)
			? own[this.df.fieldname]
			: legacy[this.doctype];
		const defaults = retail.purchase_grid_defaults?.[this.frm.doctype]?.[this.doctype];
		if (defaults && (!Array.isArray(saved) || !saved.length)) {
			// Empty preferences can reach the browser even after migration. Use
			// native saved columns when present, otherwise the shipped defaults.
			const native = legacy[this.doctype];
			saved = Array.isArray(native) && native.length ? native : defaults;
		}
		this.user_defined_columns = (Array.isArray(saved) ? saved : []).flatMap((entry) => {
			const df = this.fields_map[entry.fieldname];
			return df ? [{ ...df, columns: entry.columns, width_px: entry.width_px, in_list_view: 1 }] : [];
		});
		let fields = this.user_defined_columns.length
			? this.user_defined_columns
			: this.editable_fields || this.docfields;
		// A promotion's selected target stays visible even if saved columns omit it.
		const target = this.retail_promotion_target;
		if (target && this.fields_map[target]) {
			fields = [this.fields_map[target], ...fields.filter(field =>
				(typeof field === "string" ? field : field.fieldname) !== target)];
			if (this.user_defined_columns.length) this.user_defined_columns = fields;
		}
		this.visible_columns = [];
		const seen = new Set();
		for (const field of fields) {
			const df = typeof field === "string" ? this.fields_map[field] : field;
			if (
				!df ||
				seen.has(df.fieldname) ||
				df.hidden ||
				!(this.editable_fields || df.in_list_view) ||
				!this.frm.get_perm(df.permlevel, "read") ||
				frappe.model.layout_fields.includes(df.fieldtype)
			)
				continue;
			seen.add(df.fieldname);
			// Keep native formatters and metadata; only replace the width budget.
			this.update_default_colsize(df);
			df.colsize = Math.max(1, Math.min(12, Number(df.columns) || df.colsize || 1));
			if (df.fieldtype === "Link" && !df.formatter && df.parent) {
				const formatter = frappe.meta.docfield_map[df.parent]?.[df.fieldname]?.formatter;
				if (formatter) df.formatter = formatter;
			}
			// Item identity and Item Name are separate columns. Keep the native link
			// destination while displaying its stored code instead of the title.
			if (df.fieldname === "item_code" && df.fieldtype === "Link" && df.options === "Item") {
				df.formatter = (value, field, options, doc) =>
					frappe.form.formatters.Link(value, field, { ...options, label: value }, doc);
			}
			this.visible_columns.push([df, df.colsize]);
		}
	}

	function saveColumns(row, columns) {
		const save = retail.column_preferences?.supports(row.frm.doctype)
			? retail.column_preferences.save
			: frappe.model.user_settings.save.bind(frappe.model.user_settings);
		return save(row.frm.doctype, SETTINGS, {
			[row.grid.df.fieldname]: columns,
		}).then((r) => {
			frappe.model.user_settings[row.frm.doctype] = r.message || r;
			row.grid.reset_grid();
		});
	}

	function configureHeader(grid) {
		const row = grid.header_row;
		if (!row || row.__retail_scroll_header) return;
		row.__retail_scroll_header = true;
		row.validate_columns_width = function () {
			if (!this.selected_columns_for_grid?.length) {
				frappe.throw(__("Select at least one column."));
			}
			for (const entry of this.selected_columns_for_grid) {
				const width = Number(entry.columns);
				if (!Number.isInteger(width) || width < 1 || width > 12) {
					frappe.throw(__("Each column width must be a whole number from 1 to 12."));
				}
			}
		};
		row.update_user_settings_for_grid = function () {
			return saveColumns(this, this.selected_columns_for_grid);
		};
		row.reset_user_settings_for_grid = function () {
			return saveColumns(this, []);
		};
		// Native dialog reads global metadata widths; display this table's saved widths instead.
		const render = row.render_selected_columns;
		row.render_selected_columns = function (...args) {
			const result = render.apply(this, args);
			for (const entry of this.selected_columns_for_grid || []) {
				$(this.fields_html_wrapper)
					.find(".column-width")
					.filter(function () {
						return this.dataset.fieldname === entry.fieldname;
					})
					.val(entry.columns)
					.attr("value", entry.columns);
			}
			$(this.fields_html_wrapper).find(".column-width").on("change.retailPixels", event => {
				const entry = this.selected_columns_for_grid.find(column => column.fieldname === event.target.dataset.fieldname);
				if (entry) delete entry.width_px;
			});
			return result;
		};

		const sortColumns = row.sort_columns;
		if (sortColumns) row.sort_columns = function (...args) {
			const pixels = new Map((this.selected_columns_for_grid || []).map(entry => [entry.fieldname, entry.width_px]));
			const result = sortColumns.apply(this, args);
			for (const entry of this.selected_columns_for_grid) {
				if (Number.isFinite(pixels.get(entry.fieldname))) entry.width_px = pixels.get(entry.fieldname);
			}
			return result;
		};

		const setupDialog = row.setup_columns_for_dialog;
		if (setupDialog) row.setup_columns_for_dialog = function (...args) {
			const result = setupDialog.apply(this, args);
			for (const entry of this.selected_columns_for_grid) {
				const df = grid.visible_columns.find(([df]) => df.fieldname === entry.fieldname)?.[0];
				if (Number.isFinite(df?.width_px)) entry.width_px = df.width_px;
			}
			return result;
		};
	}

	// Measure formatted text, not the current cell box (which already has a fixed width).
	function contentWidths(grid) {
		const widths = {};
		const canvas = typeof document !== "undefined" ? document.createElement("canvas") : null;
		const context = canvas?.getContext("2d");
		const font = typeof getComputedStyle === "function"
			? getComputedStyle(grid.wrapper[0]).font : "14px sans-serif";
		if (context) context.font = font || "14px sans-serif";
		const measure = (text) => {
			const lines = String(text ?? "").split(/\r?\n/);
			return Math.max(0, ...lines.map((line) =>
				context ? context.measureText(line).width : line.length * 7));
		};
		for (const [df] of grid.visible_columns) {
			if (Number.isFinite(df.width_px)) {
				widths[df.fieldname] = df.width_px;
				continue;
			}
			if (grid.user_defined_columns?.some(column => column.fieldname === df.fieldname)) {
				widths[df.fieldname] = Math.max(1, Math.min(12, Number(df.columns) || df.colsize || 1)) * 80;
				continue;
			}
			let width = measure(__(df.label || df.fieldname)) + 40;
			for (const row of grid.grid_rows || []) {
				const value = row.doc?.[df.fieldname];
				let text = value ?? "";
				if (frappe.format && value != null) {
					const html = frappe.format(value, df, { inline: true }, row.doc);
					const element = document.createElement("div");
					element.innerHTML = html;
					text = element.textContent || "";
				}
				width = Math.max(width, measure(text) + 32);
			}
			widths[df.fieldname] = Math.ceil(Math.min(320, Math.max(64, width)));
		}
		return widths;
	}

	function styleRow(grid, row) {
		if (!row?.row) return;
		if (row.doc && !row.__retail_item_name_search && grid.fields_map.item_code?.options === "Item") {
			row.__retail_item_name_search = true;
			const makeControl = row.make_control;
			row.make_control = function (column) {
				if (column.df.fieldname !== "item_name") return makeControl.call(this, column);
				if (column.field) return;
				// A second native Item selector writes item_code, so ERPNext runs
				// the same item, UOM, price and tax handlers from either column.
				const df = { ...grid.fields_map.item_code, label: column.df.label, formatter: undefined };
				const field = frappe.ui.form.make_control({
					df, parent: column.field_area, only_input: true, with_link_btn: true,
					doc: this.doc, doctype: this.doc.doctype, docname: this.doc.name,
					frm: grid.frm, grid, grid_row: this,
				});
				field.get_query = (...args) => {
					const query = grid.get_field("item_code").get_query;
					return typeof query === "function" ? query(...args) : query;
				};
				field.is_title_link = () => true;
				field.refresh();
				field.$input?.addClass("input-sm").attr("placeholder", __("Search Item Name"));
				this.set_arrow_keys(field);
				column.field = field;
				this.on_grid_fields_dict.item_name = field;
				this.on_grid_fields.push(field);
			};
		}
		const itemColumn = grid.visible_columns.find(([df]) =>
			df.fieldname === "item_code" && df.fieldtype === "Link" && df.options === "Item");
		if (row.doc && itemColumn) {
			// Native rows keep their own field copies for subsequent refreshes.
			const field = row.docfields?.find(df => df.fieldname === "item_code");
			if (field) field.formatter = itemColumn[0].formatter;
			row.columns?.item_code?.static_area.html(
				itemColumn[0].formatter(row.doc.item_code, itemColumn[0], {}, row.doc));
		}
		const options = grid.__retail_scroll_options;
		row.row.children(".col").each(function () {
			const fieldname = this.dataset.fieldname;
			const column = grid.visible_columns.find(([df]) => df.fieldname === fieldname);
			const width = column
				? grid.__retail_content_widths?.[fieldname] || 80
				: this.classList.contains("row-index")
				? 56
				: 40;
			this.style.setProperty("--retail-column-width", `${width}px`);
			this.style.setProperty("--retail-column-grow", column && fieldname !== grid.__retail_resizing ? String(width) : "0");
			this.classList.toggle("retail-grid-data-column", Boolean(column));
			this.classList.toggle("retail-grid-pinned", fieldname === options.pin_field && grid.visible_columns[0]?.[0].fieldname === fieldname);
		});
		// Use native touch scrolling. Keep touchstart: native touch-click focus
		// handling still needs the container references initialized by that handler.
		row.row.children("[data-fieldname]").off("touchmove");
	}


	function currentColumns(grid) {
		return grid.visible_columns.map(([df]) => ({
			fieldname: df.fieldname,
			columns: Math.max(1, Math.min(12, Number(df.columns) || df.colsize || 1)),
			...(Number.isFinite(df.width_px) ? { width_px: df.width_px } : {}),
		}));
	}

	function configureDirectColumns(grid) {
		const header = grid.header_row;
		if (!header?.row?.[0] || header.__retail_direct_columns) return;
		header.__retail_direct_columns = true;
		let dragged;
		for (const cell of header.row[0].querySelectorAll(".retail-grid-data-column")) {
			cell.draggable = true;
			cell.title = __("Drag to move column; drag the edge to resize.");
			cell.addEventListener("dragstart", event => {
				dragged = cell.dataset.fieldname;
				event.dataTransfer.setData("text/plain", dragged);
				event.dataTransfer.effectAllowed = "move";
			});
			cell.addEventListener("dragover", event => {
				if (dragged) { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }
			});
			cell.addEventListener("drop", event => {
				if (!dragged) return;
				event.preventDefault();
				const columns = currentColumns(grid);
				const source = columns.findIndex(column => column.fieldname === dragged);
				const target = columns.findIndex(column => column.fieldname === cell.dataset.fieldname);
				if (source >= 0 && target >= 0 && source !== target) {
					columns.splice(target, 0, columns.splice(source, 1)[0]);
					saveColumns(header, columns);
				}
				dragged = null;
			});
			cell.addEventListener("dragend", () => { dragged = null; });
			const handle = document.createElement("span");
			handle.className = "retail-grid-resize-handle";
			handle.title = __("Drag to resize column");
			handle.addEventListener("pointerdown", event => {
				event.preventDefault();
				event.stopPropagation();
				cell.draggable = false;
				const start = event.clientX;
				const width = cell.getBoundingClientRect().width;
				const columns = currentColumns(grid);
				const column = columns.find(column => column.fieldname === cell.dataset.fieldname);
				for (const entry of columns) {
					const heading = Array.from(header.row[0].children).find(element => element.dataset.fieldname === entry.fieldname);
					entry.width_px = Math.round(heading?.getBoundingClientRect().width || grid.__retail_content_widths[entry.fieldname]);
					grid.__retail_content_widths[entry.fieldname] = entry.width_px;
				}
				grid.__retail_resizing = column.fieldname;
				const direction = frappe.utils.is_rtl() ? -1 : 1;
				const move = event => {
					const pixels = Math.round(Math.max(64, Math.min(960, width + direction * (event.clientX - start))));
					column.width_px = pixels;
					grid.__retail_content_widths[column.fieldname] = pixels;
					grid.wrapper[0].style.setProperty("--retail-grid-width", `${138 + Object.values(grid.__retail_content_widths).reduce((sum, value) => sum + value, 0)}px`);
					[header, grid.header_search, ...(grid.grid_rows || [])].forEach(row => styleRow(grid, row));
				};
				const finish = () => {
					document.removeEventListener("pointermove", move);
					document.removeEventListener("pointerup", finish);
					document.removeEventListener("pointercancel", cancel);
					cell.draggable = true;
					for (const entry of columns) {
						const heading = Array.from(header.row[0].children).find(element => element.dataset.fieldname === entry.fieldname);
						entry.width_px = Math.round(heading?.getBoundingClientRect().width || entry.width_px);
					}
					delete grid.__retail_resizing;
					saveColumns(header, columns);
				};
				const cancel = () => {
					document.removeEventListener("pointermove", move);
					document.removeEventListener("pointerup", finish);
					document.removeEventListener("pointercancel", cancel);
					cell.draggable = true;
					delete grid.__retail_resizing;
					layout(grid);
				};
				document.addEventListener("pointermove", move);
				document.addEventListener("pointerup", finish);
				document.addEventListener("pointercancel", cancel);
			});
			cell.appendChild(handle);
		}
	}

	function layout(grid) {
		if (!grid.wrapper || grid.__retail_resizing) return;
		grid.wrapper.addClass("retail-scrollable-grid");
		const container = grid.wrapper.find(".form-grid-container")[0];
		if (!container) return;
		container.setAttribute("aria-label", __("Scrollable table"));
		container.setAttribute("tabindex", "0");
		grid.__retail_content_widths = contentWidths(grid);
		const totalWidth =
			138 +
			grid.visible_columns.reduce(
				(sum, [df]) => sum + grid.__retail_content_widths[df.fieldname],
				0
			);
		grid.wrapper[0].style.setProperty("--retail-grid-width", `${totalWidth}px`);
		configureHeader(grid);
		[grid.header_row, grid.header_search, ...(grid.grid_rows || [])].forEach((row) =>
			styleRow(grid, row)
		);
		configureDirectColumns(grid);
	}

	// Link suggestions must escape the overflow viewport. Keep the original UL and
	// its native selection handlers, moving it back as soon as autocomplete closes.
	function bindInteractions(grid) {
		let popup;
		const closePopup = () => {
			if (!popup) return;
			popup.parent.appendChild(popup.list);
			popup.host.remove();
			popup = null;
			window.removeEventListener("scroll", reposition, true);
			window.removeEventListener("resize", reposition);
		};
		const reposition = () => {
			if (!popup) return;
			if (!popup.input.isConnected || popup.list.hidden) {
				closePopup();
				return;
			}
			const rect = popup.input.getBoundingClientRect();
			const viewport = grid.wrapper.find(".form-grid-container")[0].getBoundingClientRect();
			if (
				rect.right < viewport.left ||
				rect.left > viewport.right ||
				rect.bottom < 0 ||
				rect.top > innerHeight
			) {
				popup.input.dispatchEvent(new Event("blur"));
				closePopup();
				return;
			}
			const width = Math.min(Math.max(rect.width, 280), innerWidth - 16);
			const below = innerHeight - rect.bottom - 12;
			const above = below < 180 && rect.top > below;
			Object.assign(popup.host.style, {
				width: `${width}px`,
				left: `${Math.max(8, Math.min(rect.left, innerWidth - width - 8))}px`,
				top: above ? "auto" : `${rect.bottom}px`,
				bottom: above ? `${innerHeight - rect.top}px` : "auto",
			});
			popup.list.style.maxHeight = `${Math.max(
				60,
				Math.min(300, above ? rect.top - 12 : below)
			)}px`;
		};
		grid.wrapper
			.on("awesomplete-open.retailScroll", "input", function () {
				if (!this.closest(".data-row")) return;
				closePopup();
				const parent = this.closest(".awesomplete");
				const list = parent?.querySelector("ul");
				if (!list) return;
				const host = document.createElement("div");
				host.className = "awesomplete retail-grid-autocomplete";
				document.body.appendChild(host);
				host.appendChild(list);
				popup = { input: this, parent, list, host };
				reposition();
				window.addEventListener("scroll", reposition, true);
				window.addEventListener("resize", reposition);
			})
			.on("awesomplete-close.retailScroll", "input", closePopup);
		grid.wrapper.on(
			"focusin.retailScroll",
			".data-row input, .data-row select, .data-row textarea",
			function () {
				const cell = this.closest(".col");
				if (!cell || cell.classList.contains("retail-grid-pinned")) return;
				const container = grid.wrapper.find(".form-grid-container")[0];
				const bounds = container.getBoundingClientRect();
				const rect = cell.getBoundingClientRect();
				const pinned = this.closest(".data-row").querySelector(".retail-grid-pinned");
				const inset = innerWidth > 767 ? 96 + (pinned?.offsetWidth || 0) : 0;
				const rtl = frappe.utils.is_rtl();
				const left = bounds.left + (rtl ? 0 : inset);
				const right = bounds.right - (rtl ? inset : 0);
				if (rect.left < left) container.scrollLeft -= left - rect.left;
				else if (rect.right > right) container.scrollLeft += rect.right - right;
			}
		);
	}

	function enable(frm, fieldname, options = {}) {
		const grid = frm.fields_dict[fieldname]?.grid;
		// ERPNext supplies fallback templates even for editable Items grids.
		// Match native GridRow: the template is active only when editing is disabled.
		if (!grid || grid.__retail_scroll_options || (grid.template && !grid.meta?.editable_grid))
			return;
		grid.__retail_scroll_options = { pin_field: "item_code", ...options };
		grid.setup_visible_columns = setupColumns;
		// Rebuild cells only when a dynamic field change alters the layout (for
		// example, PI's Update Selling Price toggle). Other refreshes retain controls.
		const setupFields = grid.setup_fields;
		grid.setup_fields = function (...args) {
			const previous = JSON.stringify(
				(this.visible_columns || []).map(([df, width]) => [df.fieldname, width])
			);
			const result = setupFields.apply(this, args);
			this.visible_columns = [];
			this.setup_visible_columns();
			const current = JSON.stringify(
				this.visible_columns.map(([df, width]) => [df.fieldname, width])
			);
			if (previous !== current && this.grid_rows?.length) {
				this.grid_rows = [];
				this.wrapper.find(".grid-body .grid-row").remove();
			}
			return result;
		};
		const refresh = grid.refresh;
		grid.refresh = function (...args) {
			const scroll = this.wrapper?.find(".form-grid-container").scrollLeft() || 0;
			const result = refresh.apply(this, args);
			layout(this);
			this.wrapper?.find(".form-grid-container").scrollLeft(scroll);
			return result;
		};
		const fitColumns = frappe.utils.debounce(() => layout(grid), 100);
		const refreshField = grid.refresh_field;
		if (refreshField) {
			grid.refresh_field = function (...args) {
				const result = refreshField.apply(this, args);
				fitColumns();
				return result;
			};
		}
		grid.debounced_refresh = frappe.utils.debounce(grid.refresh.bind(grid), 100);
		$(frm.wrapper).on(`grid-row-render.retailScroll_${fieldname}`, (_event, row) => {
			if (row.grid === grid) {
				styleRow(grid, row);
				fitColumns();
			}
		});
		grid.reset_grid();
		bindInteractions(grid);
	}

	function register(doctype, fieldname, options = {}) {
		const key = `${doctype}:${fieldname}`;
		if (registrations.has(key)) return;
		registrations.add(key);
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				enable(frm, fieldname, options);
			},
		});
	}
	retail.scrollable_grid = { enable, register };
	function boot() {
		if (!window.frappe?.ui?.form?.on) {
			setTimeout(boot, 100);
			return;
		}
		register("Purchase Order", "items");
		register("Purchase Invoice", "items");
		register("Purchase Receipt", "items");
		register("Material Request", "items");
		register("Stock Reconciliation", "items");
		register("Stock Entry", "items");
		register("Delivery Note", "items");
		register("Sales Order", "items");
		register("Sales Invoice", "items");
		register("POS Invoice", "items");
		register("Promo Price", "products", { pin_field: "item" });
		register("Item", "custom_retail_packing_detail", {
			pin_field: "barcode",
		});
	}
	boot();
})();

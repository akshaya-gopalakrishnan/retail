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
		const saved = Object.prototype.hasOwnProperty.call(own, this.df.fieldname)
			? own[this.df.fieldname]
			: legacy[this.doctype];
		this.user_defined_columns = (Array.isArray(saved) ? saved : []).flatMap((entry) => {
			const df = this.fields_map[entry.fieldname];
			return df ? [{ ...df, columns: entry.columns, in_list_view: 1 }] : [];
		});
		const fields = this.user_defined_columns.length
			? this.user_defined_columns
			: this.editable_fields || this.docfields;
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
			this.classList.toggle("retail-grid-pinned", fieldname === options.pin_field);
		});
		// Use native touch scrolling. Keep touchstart: native touch-click focus
		// handling still needs the container references initialized by that handler.
		row.row.children("[data-fieldname]").off("touchmove");
	}

	function layout(grid) {
		if (!grid.wrapper) return;
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
	}
	boot();
})();

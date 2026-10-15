// Standard Desk lists only. Preferences are isolated by site, user and DocType.
(() => {
	const clamp = width => Math.max(70, Math.min(1200, Math.round(width)));
	const key = view => `retail:list-widths:v1:${frappe.session.user}:${view.doctype}`;
	const column_key = column => `${column.type}:${column.balance_field || column.df?.fieldname || column.type}`;
	const order_key = view => `${key(view)}:order`;
	function column_order(view) {
		if (!view._retail_list_order) {
			try {
				const saved = JSON.parse(localStorage.getItem(order_key(view)) || "[]");
				view._retail_list_order = Array.isArray(saved) ? [...new Set(saved.filter(value => typeof value === "string"))] : [];
			} catch { view._retail_list_order = []; }
		}
		const available = view.columns.map(column_key);
		// Keep personal arrangements intact; only the default puts Status last.
		if (!view._retail_list_order.length) {
			const is_status = column => column.type === "Status" || column.df?.fieldname === "status";
			return [...view.columns.filter(column => !is_status(column)),
				...view.columns.filter(is_status)].map(column_key);
		}
		return [...view._retail_list_order.filter(name => available.includes(name)), ...available.filter(name => !view._retail_list_order.includes(name))];
	}
	function save_order(view) {
		try { localStorage.setItem(order_key(view), JSON.stringify(view._retail_list_order)); }
		catch { frappe.show_alert({ message: __("Column order could not be saved in this browser."), indicator: "orange" }); }
	}
	function move_column(view, source, target) {
		const order = column_order(view);
		if (source === target || !order.includes(source) || !order.includes(target)) return;
		const source_index = order.indexOf(source), target_index = order.indexOf(target);
		[order[source_index], order[target_index]] = [order[target_index], order[source_index]];
		view._retail_list_order = order;
		save_order(view);
		apply(view);
	}
	function preferences(view) {
		if (view._retail_list_widths) return view._retail_list_widths;
		try {
			const saved = JSON.parse(localStorage.getItem(key(view)) || "{}");
			view._retail_list_widths = Object.fromEntries(Object.entries(saved || {})
				.filter(([, value]) => Number.isFinite(value)).map(([name, value]) => [name, clamp(value)]));
		} catch {
			view._retail_list_widths = {};
		}
		return view._retail_list_widths;
	}
	function save(view) {
		try { localStorage.setItem(key(view), JSON.stringify(preferences(view))); }
		catch { frappe.show_alert({ message: __("Column widths could not be saved in this browser."), indicator: "orange" }); }
	}
	function default_width(column) {
		const df = column.df || {};
		if (column.type === "Status") return 110;
		if (column.type === "Subject" && ["name", "item_code", "custom_document_code"].includes(df.fieldname)) return 140;
		if (frappe.model.is_numeric_field(df)) return 145;
		return 190;
	}
	function apply(view) {
		// Report/Kanban/Image views may inherit ListView methods but have different markup.
		if (view.view_name !== "List" || !view.$result || !view.columns) return;
		const root = view.$result[0];
		const head = root.querySelector(".list-row-head > .level-left:not(.checkbox-actions)");
		if (!head) return;
		view.$result.addClass("retail-list-widths");
		const saved = preferences(view);
		const order = column_order(view);
		const headers = Array.from(head.children).filter(el => el.classList.contains("list-row-col"));
		const widths = view.columns.map(column => saved[column_key(column)] || default_width(column));
		const visible = headers.map((el, index) => ({ el, index })).filter(({el}) => getComputedStyle(el).display !== "none");
		// Native headers have inline margins; row containers have matching padding.
		// Their gutter is outside the row width and must not be allocated to columns.
		const header_style = getComputedStyle(head.parentElement);
		const root_style = getComputedStyle(root);
		const pixels = value => parseFloat(value) || 0;
		const gutter = pixels(header_style.marginLeft) + pixels(header_style.marginRight);
		const available_width = Math.max(0, root.clientWidth - pixels(root_style.paddingLeft) - pixels(root_style.paddingRight) - gutter);
		root.style.setProperty("--retail-list-gutter", `${gutter}px`);
		// Reclaim spare space for unsized text fields; explicit widths remain exact.
		const spare = Math.max(0, available_width - 170 - visible.reduce((sum, {index}) => sum + widths[index] + 15, 0));
		const flexible = visible.filter(({index}) => !saved[column_key(view.columns[index])] && !frappe.model.is_numeric_field(view.columns[index].df || {}) && view.columns[index].type !== "Status" && !["name", "item_code", "custom_document_code"].includes(view.columns[index].df?.fieldname));
		for (const {index} of flexible) widths[index] += spare / flexible.length;
		root.style.setProperty("--retail-list-width", `${Math.floor(170 + visible.reduce((sum, {index}) => sum + widths[index] + 15, 0))}px`);
		for (const row of root.querySelectorAll(".list-row > .level-left, .list-row-head > .level-left:not(.checkbox-actions)")) {
			const cells = Array.from(row.children).filter(el => el.classList.contains("list-row-col"));
			cells.forEach((cell, index) => {
				if (widths[index]) cell.style.setProperty("--retail-list-column-width", `${widths[index]}px`);
				// Visual order only: Frappe relies on columns[0] for the subject and selection.
				if (view.columns[index]) cell.style.setProperty("--retail-list-column-order", order.indexOf(column_key(view.columns[index])));
			});
		}
		headers.forEach((cell, index) => {
			if (!view.columns[index] || cell.querySelector(".retail-list-resize")) return;
			const name = column_key(view.columns[index]);
			const grip = document.createElement("span");
			grip.className = "retail-list-reorder";
			grip.textContent = "⋮⋮";
			grip.draggable = true;
			grip.tabIndex = 0;
			grip.setAttribute("role", "button");
			grip.setAttribute("aria-label", __("Move {0}", [view.columns[index].df?.label || view.columns[index].type]));
			grip.title = __("Drag to move this column. Use arrow keys to move one position.");
			grip.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); });
			grip.addEventListener("dragstart", event => {
				if (window.innerWidth < 768) { event.preventDefault(); return; }
				event.stopPropagation();
				view._retail_drag_column = name;
				event.dataTransfer.effectAllowed = "move";
				event.dataTransfer.setData("text/plain", name);
			});
			const clear_drag = () => {
				view._retail_drag_column = null;
				for (const header of headers) header.classList.remove("retail-list-drop-target");
			};
			grip.addEventListener("dragend", clear_drag);
			cell.addEventListener("dragover", event => {
				if (!view._retail_drag_column || view._retail_drag_column === name) return;
				event.preventDefault(); event.stopPropagation();
				event.dataTransfer.dropEffect = "move";
				cell.classList.add("retail-list-drop-target");
			});
			cell.addEventListener("dragleave", () => cell.classList.remove("retail-list-drop-target"));
			cell.addEventListener("drop", event => {
				if (!view._retail_drag_column) return;
				event.preventDefault(); event.stopPropagation();
				move_column(view, view._retail_drag_column, name);
				clear_drag();
			});
			grip.addEventListener("keydown", event => {
				if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
				event.preventDefault(); event.stopPropagation();
				const visible_order = column_order(view).filter(key => {
					const index = view.columns.findIndex(column => column_key(column) === key);
				return headers[index] && getComputedStyle(headers[index]).display !== "none";
				});
				const direction = getComputedStyle(root).direction === "rtl" ? -1 : 1;
				const step = (event.key === "ArrowRight" ? 1 : -1) * direction;
				const target = visible_order[visible_order.indexOf(name) + step];
				if (!target) return;
				move_column(view, name, target);
			});
			cell.append(grip);
			const handle = document.createElement("span");
			handle.className = "retail-list-resize";
			handle.tabIndex = 0;
			handle.setAttribute("role", "separator");
			handle.setAttribute("aria-orientation", "vertical");
			handle.setAttribute("aria-label", __("Resize {0}", [view.columns[index].df?.label || view.columns[index].type]));
			handle.title = __("Drag to resize. Use arrow keys to adjust. Double-click to reset this column.");
			const change = width => {
				preferences(view)[column_key(view.columns[index])] = clamp(width);
				apply(view);
			};
			handle.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); });
			handle.addEventListener("dblclick", event => {
				event.stopPropagation();
				delete preferences(view)[column_key(view.columns[index])];
				save(view); apply(view);
			});
			handle.addEventListener("keydown", event => {
				if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
				event.preventDefault(); event.stopPropagation();
				const direction = getComputedStyle(root).direction === "rtl" ? -1 : 1;
				change(cell.getBoundingClientRect().width + (event.key === "ArrowRight" ? 10 : -10) * direction);
				save(view);
			});
			handle.addEventListener("pointerdown", event => {
				if (event.button !== 0) return;
				event.preventDefault(); event.stopPropagation();
				const start = event.clientX, width = cell.getBoundingClientRect().width;
				const direction = getComputedStyle(root).direction === "rtl" ? -1 : 1;
				handle.setPointerCapture(event.pointerId);
				const move = e => change(width + (e.clientX - start) * direction);
				const finish = () => {
					handle.removeEventListener("pointermove", move);
					handle.removeEventListener("pointerup", finish);
					handle.removeEventListener("pointercancel", finish);
					save(view);
				};
				handle.addEventListener("pointermove", move);
				handle.addEventListener("pointerup", finish);
				handle.addEventListener("pointercancel", finish);
			});
			cell.append(handle);
		});
		if (!view._retail_width_controls) {
			view._retail_width_controls = true;
			view.page.add_menu_item(__("Reset Column Widths"), () => {
				view._retail_list_widths = {}; save(view); apply(view);
			});
			view.page.add_menu_item(__("Reset Column Order"), () => {
				view._retail_list_order = []; save_order(view); apply(view);
			});
			if (window.ResizeObserver) {
				view._retail_width_observer = new ResizeObserver(() => apply(view));
				view._retail_width_observer.observe(root);
			}
		}
	}
	function install() {
		const prototype = frappe.views?.ListView?.prototype;
		if (!prototype || prototype._retail_widths_installed) return;
		prototype._retail_widths_installed = true;
		const show_list_settings = prototype.show_list_settings;
		prototype.show_list_settings = async function (...args) {
			// Property Setters do not change DocType.modified. The native metadata
			// loader can therefore reuse the old 4-10 dropdown even after a reload.
			// Fetch without cached_timestamp before the native dialog reads metadata.
			if (this._retail_loading_list_settings) return;
			this._retail_loading_list_settings = true;
			try {
				const response = await frappe.call({
					method: "frappe.desk.form.load.getdoctype",
					type: "GET",
					args: { doctype: "List View Settings" },
				});
				if (response.exc) return;
				frappe.model.set_in_localstorage("List View Settings", response.docs);
				return show_list_settings.apply(this, args);
			} finally {
				this._retail_loading_list_settings = false;
			}
		};
		for (const method of ["render_header", "render_list"]) {
			const original = prototype[method];
			prototype[method] = function (...args) {
				const result = original.apply(this, args);
				apply(this);
				return result;
			};
		}
	}
	install();
	$(install);
})();

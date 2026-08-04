frappe.pages["retail-item-family-l"].on_page_load = function(wrapper) {
	set_item_family_breadcrumbs();
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Item Family List"),
		single_column: true,
	});

	wrapper.item_family_list = new retail.ItemFamilyList(page);
};

frappe.pages["retail-item-family-l"].on_page_show = function(wrapper) {
	set_item_family_breadcrumbs();
	wrapper.item_family_list?.refresh();
};

frappe.provide("retail");

const ITEM_FAMILY_SETTINGS_KEY = "retail_item_family_list_columns";
const ITEM_FAMILY_WIDTHS_KEY = "retail_item_family_list_column_widths";
const ITEM_FAMILY_STOCK_COLUMNS_ADDED_KEY = "retail_item_family_stock_columns_added";
const ITEM_FAMILY_STATUS_COLUMN_ADDED_KEY = "retail_item_family_status_column_added";
const ITEM_FAMILY_COLUMNS = [
	{ key: "serial", label: __("No."), className: "serial-col", align: "text-right", required: true, width: 64 },
	{ key: "item", label: __("Item / Packing"), className: "item-col", required: true },
	{ key: "barcode", label: __("Barcode"), className: "barcode-col" },
	{ key: "status", label: __("Status"), className: "status-col" },
	{ key: "brand", label: __("Brand"), className: "small-col" },
	{ key: "item_group", label: __("Item Group"), className: "small-col" },
	{ key: "conversion", label: __("Conversion"), className: "number-col", align: "text-right" },
	{ key: "real_stock", label: __("Real Stock"), className: "number-col", align: "text-right", showForSaved: true },
	{ key: "in_qty", label: __("In Qty"), className: "number-col", align: "text-right", showForSaved: true },
	{ key: "out_qty", label: __("Out Qty"), className: "number-col", align: "text-right", showForSaved: true },
	{ key: "purchase_net", label: __("Purchase Excl. VAT"), className: "money-col", align: "text-right" },
	{ key: "purchase_vat", label: __("Purchase VAT"), className: "money-col", align: "text-right" },
	{ key: "purchase_gross", label: __("Purchase Incl. VAT"), className: "money-col", align: "text-right" },
	{ key: "selling_net", label: __("Selling Excl. VAT"), className: "money-col", align: "text-right" },
	{ key: "selling_vat", label: __("Selling VAT"), className: "money-col", align: "text-right" },
	{ key: "selling_gross", label: __("Selling Incl. VAT"), className: "money-col", align: "text-right" },
	{ key: "margin", label: __("Margin"), className: "money-col", align: "text-right" },
];

retail.ItemFamilyList = class ItemFamilyList {
	constructor(page) {
		this.page = page;
		this.filters = {};
		this.selected_items = new Map();
		this.visible_columns = this.get_saved_columns();
		this.column_widths = this.get_saved_widths();
		this.current_families = [];
		this.make_actions();
		this.make_body();
		this.make_filters();
		this.bind_events();
	}

	make_filters() {
		this.filters.item_name = this.make_filter("item_name", {
			fieldname: "item_name",
			label: __("Item Name"),
			fieldtype: "Data",
			placeholder: __("Item Name or Code"),
		});
		this.filters.item_group = this.make_filter("item_group", {
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
			placeholder: __("Item Group"),
		});
		this.filters.brand = this.make_filter("brand", {
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
			placeholder: __("Brand"),
		});
		this.filters.barcode = this.make_filter("barcode", {
			fieldname: "barcode",
			label: __("Barcode"),
			fieldtype: "Data",
			placeholder: __("Barcode"),
		});
		this.filters.disabled = this.make_filter("disabled", {
			fieldname: "disabled",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nEnabled\nDisabled",
			default: "Enabled",
		});
	}

	make_filter(fieldname, df) {
		const control = frappe.ui.form.make_control({
			parent: this.$filters.find(`[data-filter="${fieldname}"]`),
			df: {
				...df,
				onchange: () => this.refresh(),
			},
			render_input: true,
		});
		control.refresh();
		const placeholder = df.placeholder || df.label;
		control.$input?.attr("placeholder", placeholder);
		control.$wrapper?.attr("title", placeholder);
		return control;
	}

	make_actions() {
		this.page.set_primary_action(__("Add Item"), () => frappe.new_doc("Item"), "add");
		// Hidden for now. Uncomment if bulk Zebra label printing is needed again.
		// this.page.add_inner_button(__("Print Zebra Labels"), () => this.show_zebra_print_dialog());
		this.page.add_inner_button(__("List Settings"), () => this.show_list_settings());
		this.page.add_action_icon("refresh", () => this.refresh());
	}

	show_zebra_print_dialog() {
		retail.zebra.open_bulk_print_dialog({
			source: "item_family_list",
			source_label: __("Item Family List"),
			get_selected_items: () => Array.from(this.selected_items.values()),
			get_filters: () => this.get_filter_values(),
		});
	}

	make_body() {
		this.$body = $(`
			<div class="retail-family-page">
				<div class="retail-family-filters">
					<div data-filter="item_name"></div>
					<div data-filter="item_group"></div>
					<div data-filter="brand"></div>
					<div data-filter="barcode"></div>
					<div data-filter="disabled"></div>
					<button class="btn btn-default btn-sm retail-family-clear">${__("Clear")}</button>
					<div class="retail-family-count">0 ${__("Items")}</div>
				</div>
				<div class="retail-family-list-scroll">
					<table class="retail-family-table">
						<colgroup>${this.render_colgroup()}</colgroup>
						<thead>
							${this.render_header()}
						</thead>
						<tbody></tbody>
					</table>
				</div>
			</div>
			`).appendTo(this.page.body.empty());

		this.$filters = this.$body.find(".retail-family-filters");
		this.$count = this.$body.find(".retail-family-count");
		this.$tbody = this.$body.find("tbody");
		this.$select_all = this.$body.find(".retail-family-select-all");
	}

	get_saved_columns() {
		const defaults = ITEM_FAMILY_COLUMNS.map((column) => column.key);
		try {
			const saved = JSON.parse(localStorage.getItem(ITEM_FAMILY_SETTINGS_KEY) || "[]");
			const allowed = new Set(ITEM_FAMILY_COLUMNS.map((column) => column.key));
			const visible = saved.filter((key) => allowed.has(key));
			const should_add_stock = visible.length && !localStorage.getItem(ITEM_FAMILY_STOCK_COLUMNS_ADDED_KEY);
			const should_add_status = visible.length && !visible.includes("status") && !localStorage.getItem(ITEM_FAMILY_STATUS_COLUMN_ADDED_KEY);
			const missing_visible = should_add_stock
				? ITEM_FAMILY_COLUMNS
					.filter((column) => column.showForSaved && !visible.includes(column.key))
					.map((column) => column.key)
				: [];
			if (should_add_stock) {
				localStorage.setItem(ITEM_FAMILY_STOCK_COLUMNS_ADDED_KEY, "1");
			}
			if (should_add_status) {
				const insert_at = Math.max(visible.indexOf("barcode") + 1, 2);
				visible.splice(insert_at, 0, "status");
				localStorage.setItem(ITEM_FAMILY_STATUS_COLUMN_ADDED_KEY, "1");
			}
			return visible.length ? Array.from(new Set(["serial", "item", ...visible, ...missing_visible])) : defaults;
		} catch {
			return defaults;
		}
	}

	get_saved_widths() {
		try {
			return JSON.parse(localStorage.getItem(ITEM_FAMILY_WIDTHS_KEY) || "{}") || {};
		} catch {
			return {};
		}
	}

	save_columns(columns) {
		this.visible_columns = Array.from(new Set(["serial", "item", ...columns]));
		localStorage.setItem(ITEM_FAMILY_SETTINGS_KEY, JSON.stringify(this.visible_columns));
		this.refresh_table_structure();
		this.refresh();
	}

	get_visible_column_defs() {
		const by_key = Object.fromEntries(ITEM_FAMILY_COLUMNS.map((column) => [column.key, column]));
		return this.visible_columns.map((key) => by_key[key]).filter(Boolean);
	}

	render_colgroup() {
		return [
			`<col class="select-col">`,
			...this.get_visible_column_defs().map((column) => {
				const width = this.column_widths[column.key] || column.width;
				const style = width ? ` style="width: ${cint(width)}px"` : "";
				return `<col class="${column.className}" data-column="${column.key}"${style}>`;
			}),
		].join("");
	}

	render_header() {
		return `
			<tr>
				<th class="select-col"><input class="retail-family-select-all" type="checkbox"></th>
				${this.get_visible_column_defs()
					.map(
						(column) => `<th class="${column.align || ""}" data-column="${column.key}">
							<span class="retail-family-header-label">${column.label}</span>
							<span class="retail-family-resizer" data-column="${column.key}"></span>
						</th>`
					)
					.join("")}
			</tr>
		`;
	}

	refresh_table_structure() {
		this.$body.find("colgroup").html(this.render_colgroup());
		this.$body.find("thead").html(this.render_header());
		this.$select_all = this.$body.find(".retail-family-select-all");
		this.bind_resizers();
	}

	show_list_settings() {
		const dialog = new frappe.ui.Dialog({
			title: __("List Settings"),
			fields: [{ fieldname: "columns_html", fieldtype: "HTML" }],
			primary_action_label: __("Save"),
			primary_action: () => {
				const columns = dialog.$wrapper
					.find(".retail-family-column-row")
					.toArray()
					.filter((row) => row.querySelector("input")?.checked || row.dataset.required === "1")
					.map((row) => row.dataset.column);
				this.save_columns(columns);
				dialog.hide();
			},
		});
		dialog.$wrapper.addClass("retail-family-settings-dialog");
		dialog.show();
		this.render_column_settings(dialog);
	}

	render_column_settings(dialog) {
		const visible = new Set(this.visible_columns);
		const by_key = Object.fromEntries(ITEM_FAMILY_COLUMNS.map((column) => [column.key, column]));
		const ordered = [
			...this.visible_columns.map((key) => by_key[key]).filter(Boolean),
			...ITEM_FAMILY_COLUMNS.filter((column) => !visible.has(column.key)),
		];
		const html = `
			<div class="retail-family-column-settings">
				<div class="text-muted retail-family-column-help">${__("Drag columns to reorder. Uncheck to hide.")}</div>
				${ordered
					.map((column) => {
						const checked = column.required || visible.has(column.key) ? "checked" : "";
						const disabled = column.required ? "disabled" : "";
						return `
							<div class="retail-family-column-row" draggable="true" data-column="${column.key}" data-required="${column.required ? 1 : 0}">
								<span class="retail-family-column-grip">⋮⋮</span>
								<input type="checkbox" ${checked} ${disabled}>
								<span class="retail-family-column-label">${escape_html(column.label)}</span>
							</div>
						`;
					})
					.join("")}
			</div>
		`;
		dialog.fields_dict.columns_html.$wrapper.html(html);
		this.bind_column_settings_drag(dialog);
	}

	bind_column_settings_drag(dialog) {
		let dragged = null;
		dialog.$wrapper.find(".retail-family-column-row")
			.on("dragstart", (event) => {
				dragged = event.currentTarget;
				event.currentTarget.classList.add("is-dragging");
				event.originalEvent.dataTransfer.effectAllowed = "move";
			})
			.on("dragend", (event) => {
				event.currentTarget.classList.remove("is-dragging");
				dragged = null;
			})
			.on("dragover", (event) => {
				event.preventDefault();
				if (!dragged || dragged === event.currentTarget) return;
				const target = event.currentTarget;
				const rect = target.getBoundingClientRect();
				const after = event.originalEvent.clientY > rect.top + rect.height / 2;
				target.parentNode.insertBefore(dragged, after ? target.nextSibling : target);
			});
	}

	bind_events() {
		this.$body.on("click", ".retail-family-clear", () => this.clear_filters());
		this.$body.on("change", ".retail-family-select-all", (event) => {
			const checked = event.currentTarget.checked;
			this.$tbody.find(".family-checkbox").each((index, checkbox) => {
				checkbox.checked = checked;
				const key = get_selection_key(checkbox);
				if (checked) {
					this.selected_items.set(key, get_checkbox_selection(checkbox));
				} else {
					this.selected_items.delete(key);
				}
			});
			this.update_selection_state();
		});
		this.$body.on("change", ".family-checkbox", (event) => {
			const key = get_selection_key(event.currentTarget);
			if (event.currentTarget.checked) {
				this.selected_items.set(key, get_checkbox_selection(event.currentTarget));
			} else {
				this.selected_items.delete(key);
			}
			this.update_selection_state();
		});
		this.bind_resizers();
	}

	clear_filters() {
		Object.values(this.filters).forEach((control) => control.set_value(""));
		this.filters.disabled.set_value("Enabled");
		this.refresh();
	}

	get_filter_values() {
		const filters = {};
		Object.entries(this.filters).forEach(([fieldname, control]) => {
			const value = control.get_value();
			if (value !== undefined && value !== null && value !== "") {
				filters[fieldname] = fieldname === "disabled" ? (value === "Disabled" ? "1" : "0") : value;
			}
		});
		return filters;
	}

	refresh() {
		clearTimeout(this.refresh_timer);
		this.refresh_timer = setTimeout(() => this.load(), 150);
	}

	async load() {
		this.$tbody.html(`<tr><td colspan="${this.get_colspan()}" class="text-muted loading-row">${__("Loading")}</td></tr>`);
		const response = await frappe.call({
			method: "retail.retail_app.page.retail_item_family_l.retail_item_family_l.get_rows",
			args: { filters: this.get_filter_values() },
		});
		this.render(response.message || []);
	}

	render(families) {
		if (!families.length) {
			this.current_families = [];
			this.$tbody.html(`<tr><td colspan="${this.get_colspan()}" class="text-muted loading-row">${__("No item families found")}</td></tr>`);
			this.update_selection_state();
			return;
		}

		this.current_families = families;
		this.$tbody.html(families.map((family) => this.render_family(family)).join(""));
		this.update_selection_state();
	}

	update_selection_state() {
		this.$tbody.find(".family-checkbox").each((index, checkbox) => {
			checkbox.checked = this.selected_items.has(get_selection_key(checkbox));
			$(checkbox).closest("tr").toggleClass("selected", checkbox.checked);
		});
		const total = this.$tbody.find(".family-checkbox").length;
		const checked = this.$tbody.find(".family-checkbox:checked").length;
		this.$select_all.prop("checked", total > 0 && checked === total);
		this.$select_all.prop("indeterminate", checked > 0 && checked < total);
		this.update_count(checked, total);
	}

	update_count(selected, total) {
		const selected_text = selected ? ` | ${selected} ${__("Selected")}` : "";
		this.$count.text(`${total} ${__("Rows")}${selected_text}`);
	}

	get_colspan() {
		return this.get_visible_column_defs().length + 1;
	}

	render_family(family) {
		const serial = this.current_families.indexOf(family) + 1;
		const rows = [this.render_family_row(family, serial)];
		(family.packings || []).forEach((packing) => rows.push(this.render_packing_row(family, packing)));
		return rows.join("");
	}

	render_family_row(family, serial) {
		return `
			<tr class="family-row" data-item-code="${escape_html(family.item_code)}">
				<td class="select-col">
					<input class="family-checkbox" type="checkbox"
						data-item-code="${escape_html(family.item_code)}"
						data-row-type="item">
				</td>
				${this.render_cells(family, null, "family", serial)}
			</tr>
		`;
	}

	render_packing_row(family, packing) {
		return `
			<tr class="packing-row" data-item-code="${escape_html(family.item_code)}">
				<td class="select-col">
					<input class="family-checkbox" type="checkbox"
						data-item-code="${escape_html(family.item_code)}"
						data-row-type="packing"
						data-packing-idx="${escape_html(packing.idx)}"
						data-packing-uom="${escape_html(packing.uom)}"
						data-packing-barcode="${escape_html(packing.barcode)}">
				</td>
				${this.render_cells(family, packing, "packing", "")}
			</tr>
		`;
	}

	render_cells(family, packing, row_type, serial) {
		return this.get_visible_column_defs()
			.map((column) => `<td class="${column.align || ""}">${this.render_cell(column.key, family, packing, row_type, serial)}</td>`)
			.join("");
	}

	render_cell(key, family, packing, row_type, serial) {
		const is_packing = row_type === "packing";
		const row = packing || {};
		const values = {
			serial: is_packing ? "" : serial,
			item: is_packing
				? `<span class="packing-name">${escape_html(row.packing_name || make_packing_display_name(family, row))}</span>
					<div class="packing-parent">
						${escape_html(row.packing_code || family.item_code)}
					</div>`
				: `<a class="family-link" href="/app/item/${encodeURIComponent(family.item_code)}">
						${escape_html(family.item_name || family.item_code)}
					</a>
					<div class="family-code">${escape_html(family.item_code)}</div>`,
			barcode: escape_html(is_packing ? row.barcode : family.item_barcode),
			status: get_status(is_packing ? row.packing_disabled : family.disabled),
			brand: escape_html(family.brand),
			item_group: escape_html(family.item_group),
			conversion: is_packing ? flt(row.conversion_factor) : escape_html(family.stock_uom || ""),
			real_stock: qty(is_packing ? converted_qty(family.real_stock_qty, row.conversion_factor) : family.real_stock_qty),
			in_qty: qty(is_packing ? converted_qty(family.in_qty, row.conversion_factor) : family.in_qty),
			out_qty: qty(is_packing ? converted_qty(family.out_qty, row.conversion_factor) : family.out_qty),
			purchase_net: money(is_packing ? row.purchase_net_rate : family.purchase_net_rate),
			purchase_vat: money(is_packing ? row.purchase_vat_amount : family.purchase_vat_amount),
			purchase_gross: money(is_packing ? row.purchase_gross_rate : family.purchase_gross_rate),
			selling_net: money(is_packing ? row.selling_net_rate : family.selling_net_rate),
			selling_vat: money(is_packing ? row.selling_vat_amount : family.selling_vat_amount),
			selling_gross: money(is_packing ? row.selling_gross_rate : family.selling_gross_rate),
			margin: money(is_packing ? row.packing_margin : family.packing_margin),
		};
		return values[key] || "";
	}

	bind_resizers() {
		this.$body.find(".retail-family-resizer").off("mousedown").on("mousedown", (event) => {
			event.preventDefault();
			const column = event.currentTarget.dataset.column;
			const $th = $(event.currentTarget).closest("th");
			const start_x = event.pageX;
			const start_width = $th.outerWidth();
			$("body").addClass("retail-family-resizing");

			$(document)
				.on("mousemove.retail-family-resize", (move_event) => {
					const next_width = Math.max(56, start_width + move_event.pageX - start_x);
					this.set_column_width(column, next_width);
				})
				.on("mouseup.retail-family-resize", () => {
					$("body").removeClass("retail-family-resizing");
					localStorage.setItem(ITEM_FAMILY_WIDTHS_KEY, JSON.stringify(this.column_widths));
					$(document).off(".retail-family-resize");
				});
		});
	}

	set_column_width(column, width) {
		this.column_widths[column] = Math.round(width);
		this.$body.find(`col[data-column="${column}"]`).css("width", `${this.column_widths[column]}px`);
	}
};

function get_status(disabled) {
	return cint(disabled)
		? `<span class="indicator-pill red">${__("Disabled")}</span>`
		: `<span class="indicator-pill green">${__("Enabled")}</span>`;
}

function money(value) {
	return format_currency(flt(value), frappe.defaults.get_default("currency"));
}

function qty(value) {
	return format_number(flt(value), null, 3);
}

function converted_qty(value, conversion_factor) {
	const factor = flt(conversion_factor);
	return factor ? flt(value) / factor : flt(value);
}

function make_packing_display_name(family, row) {
	const item_name = family.item_name || family.item_code || "";
	const uom = row.uom || "";
	const conversion = flt(row.conversion_factor);
	const suffix = uom ? `${uom}${conversion ? ` x${conversion}` : ""}` : "";
	return suffix ? `${item_name} - ${suffix}` : item_name;
}

function get_selection_key(checkbox) {
	return [
		checkbox.dataset.itemCode || "",
		checkbox.dataset.rowType || "item",
		checkbox.dataset.packingIdx || "",
		checkbox.dataset.packingBarcode || "",
	].join("::");
}

function get_checkbox_selection(checkbox) {
	const selection = {
		item_code: checkbox.dataset.itemCode,
		row_type: checkbox.dataset.rowType || "item",
	};
	if (selection.row_type === "packing") {
		selection.packing_idx = cint(checkbox.dataset.packingIdx);
		selection.uom = checkbox.dataset.packingUom || "";
		selection.barcode = checkbox.dataset.packingBarcode || "";
	}
	return selection;
}

function escape_html(value) {
	if (frappe.utils?.escape_html) return frappe.utils.escape_html(String(value || ""));
	return String(value || "").replace(/[&<>"']/g, (char) => ({
		"&": "&amp;",
		"<": "&lt;",
		">": "&gt;",
		'"': "&quot;",
		"'": "&#39;",
	})[char]);
}

function set_item_family_breadcrumbs() {
	if (!frappe.breadcrumbs) return;
	frappe.breadcrumbs.add({
		type: "Custom",
		label: __("Items"),
		route: "/app/items",
	});
}

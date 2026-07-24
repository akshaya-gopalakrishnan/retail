(function () {
	frappe.provide("retail.zebra");

	retail.zebra.open_bulk_print_dialog = async function (opts) {
		const selected_items = unique_print_rows(opts.get_selected_items?.() || []);
		const source = opts.source || "item_list";
		const source_label = opts.source_label || __("Items");
		const has_selection = selected_items.length > 0;
		const scope_options = has_selection
			? `${__("Selected Items")}\n${__("Current Filtered List")}`
			: __("Current Filtered List");

		const dialog = new frappe.ui.Dialog({
			title: __("Print Zebra Labels"),
			fields: [
				{
					fieldname: "label_type",
					label: __("Label Type"),
					fieldtype: "Select",
					options: "Barcode Label\nShelf Label\nCustom",
					default: "Barcode Label",
					onchange: () => set_default_format(dialog),
				},
				{
					fieldname: "label_format",
					label: __("Label Format"),
					fieldtype: "Link",
					options: "Zebra Label Format",
					get_query: () => ({
						filters: {
							enabled: 1,
							reference_doctype: "Item",
							label_type: dialog.get_value("label_type"),
						},
					}),
				},
				{
					fieldname: "copies",
					label: __("Copies Per Item"),
					fieldtype: "Int",
					default: 1,
				},
				{
					fieldname: "currency",
					label: __("Currency"),
					fieldtype: "Data",
					default: "AED",
				},
				{
					fieldname: "scope",
					label: __("Print Scope"),
					fieldtype: "Select",
					options: scope_options,
					default: has_selection ? __("Selected Items") : __("Current Filtered List"),
					onchange: () => refresh_candidates(dialog, opts, selected_items),
				},
				{
					fieldname: "limit",
					label: __("Maximum Items"),
					fieldtype: "Int",
					default: 1000,
					description: __("Safety limit for filtered-list printing."),
					onchange: () => refresh_candidates(dialog, opts, selected_items),
				},
				{
					fieldname: "summary_html",
					fieldtype: "HTML",
				},
				{
					fieldname: "preview_html",
					fieldtype: "HTML",
				},
			],
			primary_action_label: __("Print"),
			primary_action: async () => {
				await run_zebra_dialog_action(() => print_labels(dialog, opts, selected_items, get_validated_values(dialog)));
			},
			secondary_action_label: __("Preview Sample"),
			secondary_action: () => run_zebra_dialog_action(() => preview_sample(dialog, opts, selected_items)),
		});

		dialog.show();
		dialog.fields_dict.summary_html.$wrapper.html(
			`<div class="text-muted">${__("Loading")} ${escape_html(source_label)}...</div>`
		);
		await run_zebra_dialog_action(async () => {
			await set_default_format(dialog);
			await refresh_candidates(dialog, opts, selected_items);
		});
	};

	async function run_zebra_dialog_action(action) {
		try {
			await action();
		} catch (error) {
			console.error(error);
			const message = get_error_message(error);
			frappe.msgprint({
				title: __("Zebra Print Warning"),
				message,
				indicator: "orange",
			});
		}
	}

	function get_validated_values(dialog) {
		const values = dialog.get_values(true) || {};
		const missing = [];
		if (!values.label_type) missing.push(__("Label Type"));
		if (!values.label_format) missing.push(__("Label Format"));
		if (!cint(values.copies)) missing.push(__("Copies Per Item"));
		if (!values.scope) missing.push(__("Print Scope"));
		if (!cint(values.limit)) missing.push(__("Maximum Items"));

		if (missing.length) {
			throw new Error(__("Please fill these fields: {0}", [missing.join(", ")]));
		}

		return values;
	}

	function get_error_message(error) {
		if (error?._server_messages) {
			try {
				const messages = JSON.parse(error._server_messages)
					.map((row) => JSON.parse(row).message)
					.filter(Boolean);
				if (messages.length) return messages.join("<br>");
			} catch {
				// fall through to regular message handling
			}
		}
		if (error?.message) return error.message;
		if (typeof error === "string") return error;
		return __("Could not print Zebra labels. Please check the label format and printer settings.");
	}

	async function set_default_format(dialog) {
		const label_type = dialog.get_value("label_type");
		const { message } = await frappe.call({
			method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.get_default_format",
			args: { label_type },
		});
		if (message) {
			dialog.set_value("label_format", message);
		}
	}

	async function refresh_candidates(dialog, opts, selected_items) {
		const values = dialog.get_values(true) || {};
		const args = get_candidate_args(opts, selected_items, values);
		const { message } = await frappe.call({
			method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.get_print_candidates",
			args,
		});
		render_summary(dialog, message || {}, values);
	}

	async function preview_sample(dialog, opts, selected_items) {
		const values = get_validated_values(dialog);
		const { message } = await frappe.call({
			method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.render_print_sample",
			args: {
				...get_candidate_args(opts, selected_items, values),
				label_format: values.label_format,
				copies: values.copies,
				currency: values.currency,
			},
		});
		dialog.fields_dict.preview_html.$wrapper.html(message.preview_html);
	}

	async function print_labels(dialog, opts, selected_items, values) {
		const args = {
			...get_candidate_args(opts, selected_items, values),
			label_format: values.label_format,
			copies: values.copies,
			currency: values.currency,
		};
		const { message } = await frappe.call({
			method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.print_labels",
			args,
			freeze: true,
			freeze_message: __("Sending labels to Zebra printer"),
		});
		dialog.hide();
		frappe.show_alert({ message, indicator: "green" });
	}

	function get_candidate_args(opts, selected_items, values) {
		const selected_scope = values.scope === __("Selected Items");
		return {
			source: opts.source || "item_list",
			selected_items: selected_scope ? JSON.stringify(selected_items) : "[]",
			filters: JSON.stringify(opts.get_filters?.() || {}),
			limit: values.limit || 1000,
		};
	}

	function render_summary(dialog, result, values) {
		const items = result.items || [];
		const count = cint(result.count);
		const copies = cint(values.copies || 1) || 1;
		const rows = items
			.slice(0, 10)
			.map((item) => {
				const label = [
					item.item_code,
					item.item_name,
					item.row_type === "packing" && item.uom ? __("Packing: {0}", [item.uom]) : "",
				].filter(Boolean).join(" - ");
				return `<li>${escape_html(label)}</li>`;
			})
			.join("");
		const more = result.has_more ? `<div class="text-muted">${__("Showing first 10 only.")}</div>` : "";
		dialog.fields_dict.summary_html.$wrapper.html(`
			<div class="zebra-bulk-summary" style="background:var(--subtle-fg);border:1px solid var(--border-color);border-radius:6px;padding:10px 12px;margin-bottom:10px;">
				<div><b>${count}</b> ${__("row(s) selected for printing")} x <b>${copies}</b> ${__("copies")}</div>
				<div class="text-muted">${__("Total labels")}: ${count * copies}</div>
				${rows ? `<ol style="margin:8px 0 0 18px;padding:0;">${rows}</ol>` : ""}
				${more}
			</div>
		`);
	}

	function unique_print_rows(items) {
		const seen = new Set();
		return (items || []).filter((item) => {
			const item_code = typeof item === "string" ? item : item?.item_code;
			const row_type = typeof item === "string" ? "item" : item?.row_type || "item";
			const packing_idx = typeof item === "string" ? "" : item?.packing_idx || "";
			const barcode = typeof item === "string" ? "" : item?.barcode || "";
			const key = [item_code, row_type, packing_idx, barcode].join("::");
			if (!item_code || seen.has(key)) return false;
			seen.add(key);
			return true;
		});
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
})();

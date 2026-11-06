/* Site-owned report printing; retain the report's filters, data and exports. */
(() => {
	const report_name = "Accounts Receivable";
	const default_format = "Accounts Receivable - A4";
	const settings = frappe.query_reports[report_name];
	const onload = settings.onload;
	settings.onload = async function (report) {
		await onload?.call(this, report);
		if (!report._retail_receivable_print_installed) {
			const original_format = report.get_custom_format;
			const original_template = report.get_print_template;
			report.get_custom_format = async function (print_settings) {
				if (this.report_name !== report_name) return original_format.call(this, print_settings);
				await load_company(this);
				const layout = await frappe.xcall("retail.report_print_formats.get_report_format", {
					report_name, format_name: print_settings.print_format || default_format,
				});
				// Keep CSS quotes and braces outside Frappe's JS template compiler.
				const bytes = new TextEncoder().encode(layout.css || "");
				const css = btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(""));
				return `<style>{%= new TextDecoder().decode(Uint8Array.from(atob("${css}"), (byte) => byte.charCodeAt(0))) %}</style>${layout.html}`;
			};
			report.get_print_template = function (print_settings, custom_format) {
				return this.report_name === report_name && custom_format
					? custom_format : original_template.call(this, print_settings, custom_format);
			};
			report._retail_receivable_print_installed = true;
		}
		report.menu_items = report.menu_items.map((item) => {
			if (![__("Print"), __("PDF")].includes(item.label)) return item;
			return {...item, action: () => show_dialog(report, item.label === __("PDF"))};
		});
		report.page.clear_menu();
		report.set_menu_items();
		if (frappe.model.can_write("Print Format")) {
			report.page.add_inner_button(__("Edit Print Format"), () => {
				frappe.set_route("Form", "Print Format", report.retail_receivable_print_settings?.print_format || default_format);
			});
		}
		await load_company(report);
	};

	async function load_company(report) {
		const company = report.get_filter_value("company");
		report.retail_print_company = {company_name: company || ""};
		if (!company) return;
		const {message} = await frappe.db.get_value("Company", company, ["company_name", "default_currency", "default_letter_head"]);
		if (report.get_filter_value("company") === company) report.retail_print_company = message || {company_name: company};
	}

	function show_dialog(report, pdf) {
		if (!report.data?.length) {
			frappe.msgprint(__("No outstanding entries found for the selected filters."));
			return;
		}
		const defaults = locals[":Print Settings"]?.["Print Settings"] || {};
		const previous = report.retail_receivable_print_settings || {};
		const letter_head = previous.letter_head_name || report.report_doc.letter_head
			|| report.retail_print_company?.default_letter_head || frappe.defaults.get_default("letter_head");
		const visible = report.get_visible_columns().filter((col) => col.fieldname);
		const dialog = new frappe.ui.Dialog({
			title: __("Print Settings"),
			fields: [
				{fieldname: "orientation", fieldtype: "Select", label: __("Orientation"), options: ["Landscape", "Portrait"], default: previous.orientation || "Landscape", reqd: 1},
				{fieldname: "print_format", fieldtype: "Link", label: __("Print Format"), options: "Print Format", default: previous.print_format || default_format, reqd: 1,
					get_query: () => ({filters: {print_format_for: "Report", print_format_type: "JS", report: report_name, disabled: 0}})},
				{fieldname: "with_letter_head", fieldtype: "Check", label: __("With Letter head"), default: previous.with_letter_head ?? defaults.with_letterhead ?? 0},
				{fieldname: "letter_head", fieldtype: "Link", label: __("Letter Head"), options: "Letter Head", default: letter_head, depends_on: "with_letter_head", mandatory_depends_on: "with_letter_head",
					get_query: () => ({filters: {disabled: 0}})},
				{fieldname: "include_filters", fieldtype: "Check", label: __("Include Filters"), default: previous.include_filters ?? 1},
				{fieldname: "pick_columns", fieldtype: "Check", label: __("Pick Columns"), default: previous.pick_columns || 0},
				{fieldname: "columns", fieldtype: "MultiCheck", label: __("Select Columns"), depends_on: "pick_columns", columns: 2, select_all: true,
					options: visible.map((col) => ({label: col.label, value: col.fieldname, checked: !previous.columns || previous.columns.includes(col.fieldname)}))},
			],
			primary_action_label: pdf ? __("Download PDF") : __("Print"),
			primary_action: async (values) => {
				if (values.pick_columns && !values.columns?.length) {
					frappe.msgprint(__("Select at least one column to print."));
					return;
				}
				const print_settings = {...defaults, ...values, columns: values.pick_columns ? values.columns : null,
					letter_head: null, letter_head_name: values.with_letter_head ? values.letter_head : null};
				report.retail_receivable_print_settings = {...values, letter_head_name: print_settings.letter_head_name};
				dialog.hide();
				await (pdf ? report.pdf_report(print_settings) : report.print_report(print_settings));
			},
			...(frappe.model.can_write("Print Format") ? {
				secondary_action_label: __("Edit Print Format"),
				secondary_action: () => {
					const name = dialog.get_value("print_format");
					if (name) { dialog.hide(); frappe.set_route("Form", "Print Format", name); }
				},
			} : {}),
		});
		dialog.show();
		return dialog;
	}
})();

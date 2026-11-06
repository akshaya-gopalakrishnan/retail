frappe.query_reports["Daily Sales Summary"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	async onload(report) {
		report.report_settings.setup_printing(report);
		await report.report_settings.load_print_company(report);
	},
	setup_printing(report) {
		const report_name = "Daily Sales Summary";
		const default_format = "Daily Sales Summary - A4";
		if (!report._retail_sales_print_installed) {
			const original_format = report.get_custom_format;
			const original_template = report.get_print_template;
			// QueryReport is reused between routes. Other reports keep native methods.
			report.get_custom_format = async function (settings) {
				if (this.report_name !== report_name) return original_format.call(this, settings);
				const layout = await frappe.xcall("retail.report_print_formats.get_report_format", {
					report_name,
					format_name: settings.print_format || default_format,
				});
				// Custom CSS is plain text, not a JS template. Keep quoted font names
				// and CSS braces out of the template compiler, including after UI edits.
				const bytes = new TextEncoder().encode(layout.css || "");
				const css = btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(""));
				return `<style>{%= new TextDecoder().decode(Uint8Array.from(atob("${css}"), (byte) => byte.charCodeAt(0))) %}</style>${layout.html}`;
			};
			report.get_print_template = function (settings, custom_format) {
				return this.report_name === report_name && custom_format
					? custom_format
					: original_template.call(this, settings, custom_format);
			};
			report._retail_sales_print_installed = true;
		}
		report.menu_items = report.menu_items.map((item) => {
			if (![__("Print"), __("PDF")].includes(item.label)) return item;
			return {
				...item,
				action: () => report.report_settings.show_print_dialog(report, item.label === __("PDF")),
			};
		});
		report.page.clear_menu();
		report.set_menu_items();
		if (frappe.model.can_write("Print Format")) {
			report.page.add_inner_button(__("Edit Print Format"), () => {
				frappe.set_route("Form", "Print Format", report.retail_sales_print_settings?.print_format || default_format);
			});
		}
	},
	show_print_dialog(report, pdf) {
		const defaults = locals[":Print Settings"]?.["Print Settings"] || {};
		const previous = report.retail_sales_print_settings || {};
		const visible_columns = report.get_visible_columns().filter((col) => col.fieldname);
		const letter_head = previous.letter_head_name || report.report_doc.letter_head
			|| report.retail_print_company?.default_letter_head || frappe.defaults.get_default("letter_head");
		const dialog = new frappe.ui.Dialog({
			title: __("Print Settings"),
			fields: [
				{fieldname: "orientation", fieldtype: "Select", label: __("Orientation"),
					options: ["Landscape", "Portrait"], default: previous.orientation || "Landscape", reqd: 1},
				{fieldname: "print_format", fieldtype: "Link", label: __("Print Format"), options: "Print Format",
					default: previous.print_format || "Daily Sales Summary - A4", reqd: 1,
					get_query: () => ({filters: {print_format_for: "Report", print_format_type: "JS", report: report.report_name, disabled: 0}})},
				{fieldname: "with_letter_head", fieldtype: "Check", label: __("With Letter head"),
					default: previous.with_letter_head ?? defaults.with_letterhead ?? 0},
				{fieldname: "letter_head", fieldtype: "Link", label: __("Letter Head"), options: "Letter Head",
					default: letter_head, depends_on: "with_letter_head", mandatory_depends_on: "with_letter_head",
					get_query: () => ({filters: {disabled: 0}})},
				{fieldname: "include_filters", fieldtype: "Check", label: __("Include Filters"),
					default: previous.include_filters ?? 1},
				{fieldname: "pick_columns", fieldtype: "Check", label: __("Pick Columns"), default: previous.pick_columns || 0},
				{fieldname: "columns", fieldtype: "MultiCheck", label: __("Select Columns"), depends_on: "pick_columns",
					columns: 2, select_all: true,
					options: visible_columns.map((col) => ({label: col.label, value: col.fieldname,
						checked: !previous.columns || previous.columns.includes(col.fieldname)}))},
			],
			primary_action_label: pdf ? __("Download PDF") : __("Print"),
			primary_action: async (values) => {
				if (values.pick_columns && !values.columns?.length) {
					frappe.msgprint(__("Select at least one column to print."));
					return;
				}
				const settings = {
					...defaults,
					...values,
					columns: values.pick_columns ? values.columns : null,
					letter_head: null,
					letter_head_name: values.with_letter_head ? values.letter_head : null,
				};
				report.retail_sales_print_settings = {...values, letter_head_name: settings.letter_head_name};
				dialog.hide();
				await (pdf ? report.pdf_report(settings) : report.print_report(settings));
			},
			...(frappe.model.can_write("Print Format") ? {
				secondary_action_label: __("Edit Print Format"),
				secondary_action: () => {
					const name = dialog.get_value("print_format");
					if (name) {
						dialog.hide();
						frappe.set_route("Form", "Print Format", name);
					}
				},
			} : {}),
		});
		dialog.show();
		return dialog;
	},
	async load_print_company(report) {
		const company = report.get_filter_value("company");
		report.retail_print_company = { company_name: company || "" };
		if (!company) return;
		const { message } = await frappe.db.get_value("Company", company, [
			"company_name",
			"default_currency",
			"default_letter_head",
		]);
		if (report.get_filter_value("company") === company) {
			report.retail_print_company = message || { company_name: company };
		}
	},
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			async on_change(report) {
				await report.report_settings.load_print_company(report);
				return report.refresh();
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "counter",
			label: __("Counter"),
			fieldtype: "Link",
			options: "Counter",
		},
	],
};

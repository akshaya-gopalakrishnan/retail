frappe.query_reports["Tax Payable Report Summary"] = {
	onload: function (report) {
		include_checkbox_filters(report);
		add_tax_report_print_buttons(report, "Portrait");
	},
	refresh: function (report) {
		add_tax_report_print_buttons(report, "Portrait");
	},
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
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
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center",
			get_query: function () {
				return {
					filters: {
						company: frappe.query_report.get_filter_value("company"),
						is_group: 0,
					},
				};
			},
		},
		{
			fieldname: "show_zero_tax_rows",
			label: __("Show Zero Tax Rows"),
			fieldtype: "Check",
			default: 1,
			on_change: function (report) {
				report.refresh(true);
			},
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (data && data.is_group) {
			value = $(`<span>${value || ""}</span>`).css("font-weight", "600").wrap("<p></p>").parent().html();
		}

		return value;
	},
};

function include_checkbox_filters(report) {
	if (report._tax_payable_report_summary_checkbox_filters_included) {
		return;
	}

	const original_get_filter_values = report.get_filter_values.bind(report);
	report.get_filter_values = function (raise) {
		const values = original_get_filter_values(raise);
		values.show_zero_tax_rows = cint(report.get_filter_value("show_zero_tax_rows", false));
		return values;
	};
	report._tax_payable_report_summary_checkbox_filters_included = true;
}

function add_tax_report_print_buttons(report, orientation) {
	if (report._custom_tax_report_print_buttons_added) {
		return;
	}

	const add_buttons = () => {
		if (!report.page) {
			setTimeout(add_buttons, 300);
			return;
		}

		const show_print_settings = (callback) => {
			frappe.ui.get_print_settings(
				false,
				(print_settings) => {
					print_settings.orientation = orientation;
					print_settings.include_filters = 0;
					print_settings.print_format = null;
					print_settings.report = null;
					print_settings.columns = [];
					print_settings.pick_columns = 0;
					callback(print_settings);
				},
				report.report_doc.letter_head,
				false,
				false
			);
		};

		const print_action = () => show_print_settings((settings) => report.print_report(settings));
		const pdf_action = () => show_print_settings((settings) => report.pdf_report(settings));

		report.page.add_inner_button(__("Custom Print"), print_action);
		report.page.add_inner_button(__("Custom PDF"), pdf_action);
		report.page.add_menu_item(__("Custom Print"), print_action);
		report.page.add_menu_item(__("Custom PDF"), pdf_action);
		report._custom_tax_report_print_buttons_added = true;
	};

	setTimeout(add_buttons, 300);
}

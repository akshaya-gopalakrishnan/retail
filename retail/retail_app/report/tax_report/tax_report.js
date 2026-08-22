frappe.query_reports["Tax Report"] = {
	onload: function (report) {
		include_checkbox_filters(report);
		set_party_filter_options(report);
		add_tax_report_print_buttons(report, "Landscape");
	},
	refresh: function (report) {
		add_tax_report_print_buttons(report, "Landscape");
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
			fieldname: "transaction_type",
			label: __("Transaction Type"),
			fieldtype: "Select",
			options: "\nPOS Sales\nPOS Sales Return\nSales Invoice\nSales Return\nPurchase Invoice\nPurchase Return\nExpense\nTax Adjustment",
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Select",
			options: ["", "Customer", "Supplier"],
			on_change: function (report) {
				set_party_filter_options(report);
				Promise.resolve(report.set_filter_value("party", "")).then(() => report.refresh(true));
			},
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Link",
			options: "Customer",
			get_query: function () {
				const party_type = frappe.query_report.get_filter_value("party_type") || "Customer";
				const filters = {};
				if (party_type === "Customer") {
					filters.disabled = 0;
				} else if (party_type === "Supplier") {
					filters.disabled = 0;
				}
				return { doctype: party_type, filters };
			},
		},
		{
			fieldname: "tax_account",
			label: __("Tax Account"),
			fieldtype: "Link",
			options: "Account",
			get_query: function () {
				return {
					filters: {
						company: frappe.query_report.get_filter_value("company"),
						account_type: "Tax",
						is_group: 0,
					},
				};
			},
		},
		{
			fieldname: "show_zero_vat_rows",
			label: __("Show Zero Tax Rows"),
			fieldtype: "Check",
			default: 0,
			on_change: function (report) {
				report.refresh(true);
			},
		},
		{
			fieldname: "show_summary_rows",
			label: __("Show Summary Rows"),
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

function set_party_filter_options(report) {
	const party_type = report.get_filter_value("party_type") || "Customer";
	const party_filter = report.get_filter("party");

	if (!party_filter) {
		return;
	}

	party_filter.df.options = party_type;
	party_filter.$input && party_filter.$input.attr("data-target", party_type);
	if (party_filter.$input) {
		party_filter.$input.cache = {};
	}
	if (party_filter.awesomplete) {
		party_filter.awesomplete.list = [];
	}
	party_filter.refresh();
}

function include_checkbox_filters(report) {
	if (report._tax_report_checkbox_filters_included) {
		return;
	}

	const original_get_filter_values = report.get_filter_values.bind(report);
	report.get_filter_values = function (raise) {
		const values = original_get_filter_values(raise);
		values.show_zero_vat_rows = cint(report.get_filter_value("show_zero_vat_rows", false));
		values.show_summary_rows = cint(report.get_filter_value("show_summary_rows", false));
		return values;
	};
	report._tax_report_checkbox_filters_included = true;
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

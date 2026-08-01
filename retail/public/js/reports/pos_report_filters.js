window.get_pos_report_filters = function get_pos_report_filters(options = {}) {
	const filters = [
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
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
		{
			fieldname: "counter",
			label: __("Counter"),
			fieldtype: "Link",
			options: "POS Branch Counter",
			get_query: function () {
				const branch = frappe.query_report.get_filter_value("branch");
				return branch ? { filters: { branch } } : {};
			},
		},
		{ fieldname: "pos_profile", label: __("POS Profile"), fieldtype: "Link", options: "POS Profile" },
	];

	if (options.include_cashier) {
		filters.push(
			{
				fieldname: "cashier_employee",
				label: __("Cashier Employee"),
				fieldtype: "Link",
				options: "Employee",
			},
			{ fieldname: "cashier", label: __("Cashier User"), fieldtype: "Link", options: "User" }
		);
	}

	if (options.include_customer) {
		filters.push({ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" });
	}

	if (options.include_item_filters) {
		filters.push(
			{ fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item" },
			{ fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
			{ fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse" }
		);
	} else if (options.include_item_group) {
		filters.push({ fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" });
	}

	if (options.include_shift) {
		filters.push({ fieldname: "shift", label: __("Shift"), fieldtype: "Link", options: "POS Cashier Shift" });
	}

	if (options.include_payment_mode) {
		filters.push({
			fieldname: "payment_mode",
			label: __("Mode of Payment"),
			fieldtype: "Link",
			options: "Mode of Payment",
		});
	}

	if (options.include_status) {
		filters.push({
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nPaid\nConsolidated\nReturn\nCancelled",
		});
	}

	if (options.include_movement_type) {
		filters.push({
			fieldname: "movement_type",
			label: __("Movement Type"),
			fieldtype: "Select",
			options: "\nCash In\nCash Out",
		});
	}

	return filters;
};

frappe.provide("retail");

retail.van_sales_report_filters = function() {
	return [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
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
			fieldname: "van_session",
			label: __("Van Session"),
			fieldtype: "Link",
			options: "Van Session",
		},
		{
			fieldname: "van",
			label: __("Van"),
			fieldtype: "Link",
			options: "Van Fleet",
		},
		{
			fieldname: "driver",
			label: __("Driver"),
			fieldtype: "Link",
			options: "Driver",
		},
	];
};

retail.VanDocumentWrapper = class VanDocumentWrapper {
	constructor(options) {
		this.options = options;
		this.page = options.page;
		this.options.set_van_breadcrumbs = () => this.set_van_breadcrumbs();
		this.make_list_view();
		setTimeout(() => this.set_van_breadcrumbs(), 100);
		setTimeout(() => this.set_van_breadcrumbs(), 500);
		frappe.after_ajax?.(() => this.set_van_breadcrumbs());
	}

	set_van_breadcrumbs() {
		frappe.breadcrumbs.add({
			type: "Custom",
			route: "/app/van-sales",
			label: __("Van Sales"),
		});
	}

	make_list_view() {
		const wrapper_options = this.options;

		class VanListView extends frappe.views.ListView {
			setup_defaults() {
				return Promise.resolve(super.setup_defaults()).then(() => {
					this.page_title = wrapper_options.title || this.page_title;
					this.filters = this.with_wrapper_filters(this.filters || []);
					this.sort_by = wrapper_options.sort_by || this.sort_by;
					this.sort_order = wrapper_options.sort_order || this.sort_order;
				});
			}

			async set_fields() {
				await super.set_fields();
				(wrapper_options.fields || [])
					.filter((fieldname) => frappe.meta.has_field(this.doctype, fieldname) || frappe.model.std_fields_list.includes(fieldname))
					.forEach((fieldname) => this._add_field(fieldname));
				this.build_fields();
			}

			setup_columns() {
				super.setup_columns();
				if (!Array.isArray(wrapper_options.columns) || !wrapper_options.columns.length) return;

				if (wrapper_options.hide_scope_filter) {
					this.retail_fit_columns = true;
					this.retail_list_activity_width = 90;
					const compact_widths = {
						name: 90, title: 180, transaction_date: 100, status: 110,
						custom_van_request_type: 95, custom_van_session: 95,
						custom_van: 110, custom_van_warehouse: 175, custom_driver_name: 130,
					};
					this.columns.forEach((column) => {
						const field = column.df?.fieldname || column.fieldname;
						column.retail_compact_width = compact_widths[field] || 100;
						column.retail_min_width = field === "title" || field === "custom_van_warehouse" ? 110 : 70;
					});
				}

				const existing = new Set((this.columns || []).map((column) => column.df?.fieldname || column.fieldname));
				const metaFields = new Map((this.meta?.fields || []).map((df) => [df.fieldname, df]));

				wrapper_options.columns.forEach((column) => {
					if (!column.fieldname || existing.has(column.fieldname)) return;
					const metaField = metaFields.get(column.fieldname) || {};
					if (!metaField.fieldname && !frappe.model.std_fields_list.includes(column.fieldname)) return;
					const df = {
						fieldname: column.fieldname,
						label: column.label || metaField.label || column.fieldname,
						fieldtype: column.type || metaField.fieldtype || "Data",
						options: column.options || metaField.options,
					};
					this.columns.push({
						type: "Field",
						...(wrapper_options.hide_scope_filter ? {
							retail_compact_width: column.fieldname === "custom_van_warehouse" ? 175 : column.fieldname === "custom_driver_name" ? 130 : 100,
							retail_min_width: column.fieldname === "custom_van_warehouse" ? 110 : 70,
						} : {}),
						df,
					});
				});
			}

			with_wrapper_filters(filters) {
				const van_filter = [
					this.doctype,
					wrapper_options.flag_field,
					"=",
					wrapper_options.flag_value === undefined ? 1 : wrapper_options.flag_value,
				];
				const blocked_fields = new Set([wrapper_options.flag_field, ...(wrapper_options.clear_fields || [])]);
				return [
					...(wrapper_options.hide_scope_filter ? [] : [van_filter]),
					...filters.filter((filter) => Array.isArray(filter) && !blocked_fields.has(filter[1])),
				];
			}

			async setup_filter_area() {
				await super.setup_filter_area();
				if (!wrapper_options.hide_scope_filter || !this.filter_area?.filter_list) return;
				const group = this.filter_area.filter_list;
				// This dedicated page keeps its filter editor, without an applied-filter badge.
				group.update_filter_button = function() {
					this.filter_button.removeClass("btn-primary-light").addClass("btn-default");
					this.filter_button.find(".filter-icon").removeClass("active");
					this.filter_button.find(".button-label").text(__("Filter"));
					this.filter_button.attr("title", __("Filter"));
					const has_user_filters = this.filters.some(
						(filter) => filter.fieldname !== wrapper_options.flag_field
					) || Boolean(this.base_list?.filter_area?.get_standard_filters().length);
					this.filter_x_button?.toggle(has_user_filters);
				};
				group.update_filter_button();
			}

			get_filters_for_args() {
				const filters = super.get_filters_for_args();
				if (!wrapper_options.hide_scope_filter) return filters;
				// The Van Sales scope belongs to this page, not the user's filters.
				return [
					[this.doctype, wrapper_options.flag_field, "=",
						wrapper_options.flag_value === undefined ? 1 : wrapper_options.flag_value],
					...filters.filter((filter) => filter[1] !== wrapper_options.flag_field),
				];
			}

			set_title() {
				this.page.set_title(wrapper_options.title || this.page_title, null, true, "", this.meta?.description);
			}

			set_breadcrumbs() {
				wrapper_options.set_van_breadcrumbs?.();
			}

			set_primary_action() {
				if (!this.can_create || frappe.boot.read_only) {
					this.page.clear_primary_action();
					return;
				}

				this.page.set_primary_action(
					`${__("Add")} ${wrapper_options.title || __(this.doctype)}`,
					() => this.make_new_doc(),
					"add"
				);
			}

			make_new_doc() {
				frappe.route_options = { ...(wrapper_options.new_doc_values || {}) };
				frappe.new_doc(this.doctype);
			}
		}

		this.list_view = new VanListView({
			doctype: this.options.doctype,
			parent: this.page.parent,
			page_title: this.options.title,
		});
		this.list_view.init_promise?.catch((error) => {
			console.error(`Unable to render ${this.options.title || this.options.doctype}`, error);
			$(this.page.main || this.page.body).html(
				`<div class="text-muted p-4">${__("Unable to load this Van Sales page. Please refresh and try again.")}</div>`
			);
		});
	}

	refresh() {
		this.set_van_breadcrumbs();
		this.list_view?.refresh();
	}
};

(function() {
	frappe.pages = frappe.pages || {};
	frappe.standard_pages = frappe.standard_pages || {};

	const page_specs = {
		"van-stock-request": {
			hide_scope_filter: true,
			title: __("Stock Request"),
			doctype: "Material Request",
			flag_field: "custom_is_van_stock_request",
			list_title: __("Stock Request"),
			new_doc_values: {
				custom_is_van_stock_request: 1,
				material_request_type: "Material Transfer",
				custom_van_request_type: "Loading",
			},
			columns: [
				{ fieldname: "name", label: __("Request"), link: true },
				{ fieldname: "transaction_date", label: __("Date"), type: "Date" },
				{ fieldname: "custom_van_request_type", label: __("Type") },
				{ fieldname: "custom_van_session", label: __("Session") },
				{ fieldname: "custom_van", label: __("Van") },
				{ fieldname: "custom_van_warehouse", label: __("Warehouse") },
				{ fieldname: "custom_driver_name", label: __("Driver") },
				{ fieldname: "status", label: __("Status") },
			],
			fields: [
				"name",
				"transaction_date",
				"custom_van_request_type",
				"custom_van_session",
				"custom_van",
				"custom_van_warehouse",
				"custom_driver_name",
				"status",
			],
		},
		"van-stock-entries": {
			title: __("Van Stock Entries"),
			doctype: "Stock Entry",
			flag_field: "custom_is_van_stock_entry",
			list_title: __("Van Stock Entry"),
			new_doc_values: {
				custom_is_van_stock_entry: 1,
			},
			columns: [
				{ fieldname: "name", label: __("Stock Entry"), link: true },
				{ fieldname: "posting_date", label: __("Date"), type: "Date" },
				{ fieldname: "stock_entry_type", label: __("Stock Entry Type") },
				{ fieldname: "custom_van_stock_entry_type", label: __("Van Type") },
				{ fieldname: "custom_van_session", label: __("Session") },
				{ fieldname: "docstatus", label: __("Status"), type: "DocStatus" },
			],
			fields: ["name", "posting_date", "stock_entry_type", "custom_van_stock_entry_type", "custom_van_session", "docstatus"],
		},
		"retail-van-sales-invoice": {
			title: __("Van Sales Invoice"),
			doctype: "Sales Invoice",
			flag_field: "custom_is_van_sale",
			clear_fields: ["is_return"],
			list_title: __("Van Sales Invoice"),
			new_doc_values: {
				custom_is_van_sale: 1,
				update_stock: 1,
			},
			columns: [
				{ fieldname: "name", label: __("Invoice"), link: true },
				{ fieldname: "posting_date", label: __("Date"), type: "Date" },
				{ fieldname: "customer_name", label: __("Customer") },
				{ fieldname: "custom_van_session", label: __("Session") },
				{ fieldname: "grand_total", label: __("Grand Total"), type: "Currency" },
				{ fieldname: "outstanding_amount", label: __("Outstanding"), type: "Currency" },
				{ fieldname: "status", label: __("Status") },
			],
			fields: ["name", "posting_date", "customer_name", "custom_van_session", "grand_total", "outstanding_amount", "status"],
		},
		"van-payments": {
			title: __("Van Payments"),
			doctype: "Payment Entry",
			flag_field: "custom_is_van_payment",
			list_title: __("Van Payment"),
			new_doc_values: {
				custom_is_van_payment: 1,
				payment_type: "Receive",
			},
			columns: [
				{ fieldname: "name", label: __("Payment"), link: true },
				{ fieldname: "posting_date", label: __("Date"), type: "Date" },
				{ fieldname: "payment_type", label: __("Type") },
				{ fieldname: "party", label: __("Party") },
				{ fieldname: "mode_of_payment", label: __("Mode") },
				{ fieldname: "paid_amount", label: __("Paid Amount"), type: "Currency" },
				{ fieldname: "custom_van_session", label: __("Session") },
			],
			fields: ["name", "posting_date", "payment_type", "party", "mode_of_payment", "paid_amount", "custom_van_session"],
		},
	};

	Object.keys(page_specs).forEach((route) => {
		const spec = page_specs[route];

		frappe.standard_pages[route] = function() {
			const wrapper = frappe.container.add_page(route);
			frappe.pages[route] = wrapper;
			wrapper.on_page_load = function(page_wrapper) {
				const page = frappe.ui.make_app_page({
					parent: page_wrapper,
					title: spec.title,
					single_column: false,
				});

				try {
					page_wrapper.van_sales_wrapper = new retail.VanDocumentWrapper({
						page,
						doctype: spec.doctype,
						flag_field: spec.flag_field,
						flag_value: spec.flag_value,
						hide_scope_filter: spec.hide_scope_filter,
						clear_fields: spec.clear_fields,
						title: spec.list_title,
						new_doc_values: spec.new_doc_values,
						columns: spec.columns,
						fields: spec.fields,
						sort_by: spec.sort_by,
						sort_order: spec.sort_order,
					});
				} catch (error) {
					console.error(`Unable to render ${route}`, error);
					$(page.body).html(`<div class="text-muted p-4">${__("Unable to load this Van Sales page. Please refresh and try again.")}</div>`);
				}
			};
			wrapper.on_page_show = function(page_wrapper) {
				page_wrapper.van_sales_wrapper?.refresh();
			};
			wrapper.on_page_load(wrapper);
			$(wrapper).on("show", function() {
				wrapper.on_page_show?.(wrapper);
			});
		};
	});
})();

frappe.query_reports["Promotion Performance"] = {
    filters: [
        {fieldname: "view", label: __("View"), fieldtype: "Select", options: "Summary\nDetail", default: "Summary"},
        {fieldname: "compare_previous", label: __("Compare Previous Equal Period"), fieldtype: "Check", default: 1},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start()},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today()},
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company")},
        {fieldname: "pos_branch", label: __("Branch"), fieldtype: "Link", options: "Branch"},
        {fieldname: "pos_counter", label: __("Counter"), fieldtype: "Link", options: "POS Branch Counter"},
        {
            fieldname: "pos_cashier", label: __("Cashier"), fieldtype: "Autocomplete",
            get_query: () => ({
                query: "retail.retail_app.report.promotion_performance.promotion_performance.get_cashiers",
                params: {company: frappe.query_report.get_filter_value("company")}
            })
        },
        {
            fieldname: "promotion", label: __("Promotion"), fieldtype: "Autocomplete",
            get_query: () => ({query: "retail.retail_app.report.promotion_sales_detail.promotion_sales_detail.get_promotions"})
        }
    ]
};

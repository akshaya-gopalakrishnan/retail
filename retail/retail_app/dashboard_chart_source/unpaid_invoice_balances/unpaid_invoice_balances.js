frappe.provide("frappe.dashboards.chart_sources");
frappe.dashboards.chart_sources["Unpaid Invoice Balances"] = {
    method: "retail.accounts_workspace_chart.get_data",
    filters: [{fieldname: "company", label: __("Company"), fieldtype: "Link",
        options: "Company", reqd: 1, default: frappe.defaults.get_user_default("Company")}],
};

frappe.query_reports["POS Settlement Audit"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company")},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.get_today()},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today()},
        {fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer"}
    ]
};

{% include "retail/retail_app/report/slow_moving_items/slow_moving_items.js" %}

frappe.query_reports["Supplier Stock"] = {
    ...frappe.query_reports["Slow Moving Items"],
    filters: frappe.query_reports["Slow Moving Items"].filters.map(filter => ({
        ...filter,
        ...(["max_net_qty", "limit"].includes(filter.fieldname) ? { default: 0 } : {}),
    })),
};

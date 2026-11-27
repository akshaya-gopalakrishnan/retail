frappe.listview_settings["Van Sales Sync Log"] = {
    add_fields: ["status"],
    get_indicator(doc) {
        const colors = {Success: "green", Failed: "red", Duplicate: "blue", Pending: "orange"};
        return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
    },
};

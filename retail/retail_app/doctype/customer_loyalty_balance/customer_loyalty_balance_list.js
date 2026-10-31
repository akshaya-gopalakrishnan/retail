frappe.listview_settings['Customer Loyalty Balance'] = {
    hide_name_column: true,
    hide_name_filter: true,
    onload(view) {
        view.page.set_title(__('Loyalty Point Entry'));
        // Keep all four point totals visible with the customer ID and name.
        view.list_view_settings.total_fields = 8;
        view.setup_columns();
        view.render_header(true);
    },
};

(() => {
    const defaultBranch = () => frappe.boot?.retail_restaurant_default_branch;
    frappe.ui.form.on("Restaurant Table", {
        onload(frm) {
            if (frm.is_new() && !frm.doc.branch && defaultBranch()) {
                frm.set_value("branch", defaultBranch());
            }
        },
    });
    frappe.ui.form.RestaurantTableQuickEntryForm = class extends frappe.ui.form.QuickEntryForm {
        render_dialog() {
            super.render_dialog();
            if (this.doc.__islocal && !this.dialog.get_value("branch") && defaultBranch()) {
                this.dialog.set_value("branch", defaultBranch());
            }
        }
    };
})();

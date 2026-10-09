// Keep native ERP forms and editors; only their permission state changes.
frappe.ui.form.on("User", {
    refresh(frm) {
        if (frappe.boot.can_manage_access) return;
        frm.can_edit_roles = false;
        for (const field of ["role_profile_name", "module_profile", "roles", "block_modules", "user_emails"]) {
            frm.toggle_enable(field, false);
        }
        if (!frm.is_new()) frm.toggle_enable("user_type", false);
        for (const editor of [frm.roles_editor, frm.module_editor]) {
            if (editor) {
                editor.disable = true;
                editor.show();
            }
        }
    },
});

frappe.ui.form.on("Employee", {
    refresh(frm) {
        frm.toggle_enable("pos_operator_privilege", Boolean(frappe.boot.can_manage_access));
    },
});

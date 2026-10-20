// Keep native User editors, filtered by the server to the actor's assigned access.
frappe.ui.form.on("User", {
    refresh(frm) {
        if (frappe.boot.can_manage_access) return;
        const canManage = Boolean(frappe.boot.can_delegate_access && frm.doc.name !== frappe.session.user &&
            (frm.is_new() || frm.doc.retail_access_manager === frappe.session.user ||
                (!frm.doc.retail_access_manager && frm.doc.owner === frappe.session.user)));
        frm.can_edit_roles = canManage;
        // Presets define security rules; staff assignment uses the filtered checkboxes.
        frm.toggle_display(["role_profile_name", "module_profile", "retail_access_manager", "sb_allow_modules", "modules_html"], false);
        // The Retail checklist is the staff-facing module/menu editor. Native
        // framework module blocks are inherited and remain enforced underneath.
        frm.set_df_property("retail_sidebar_permissions_section", "label", __("Allow Modules"));
        frm.toggle_enable(["roles", "block_modules", "user_emails"], canManage);
        if (!frm.is_new()) frm.toggle_enable("user_type", canManage);
        for (const editor of [frm.roles_editor, frm.module_editor]) {
            if (editor) {
                editor.disable = !canManage;
                editor.show();
            }
        }
        frm.roles_editor?.multicheck?.$select_buttons?.toggle(canManage);
        if (frm.roles_editor && !frm.roles_editor.retail_delegate_change) {
            const control = frm.roles_editor.multicheck;
            const original = control.df.on_change;
            control.df.on_change = function () {
                if (frm.can_edit_roles) frm.doc.role_profile_name = null;
                original.call(this);
            };
            frm.roles_editor.retail_delegate_change = true;
        }
        // The security-rule editor remains with Super Admin; staff checkboxes are here.
        frm.remove_custom_button(__("Set User Permissions"), __("Permissions"));
    },
});

frappe.ui.form.on("Employee", {
    refresh(frm) {
        frm.toggle_enable("pos_operator_privilege", Boolean(frappe.boot.can_manage_access || frappe.user.has_role("Customer Administrator")));
    },
});

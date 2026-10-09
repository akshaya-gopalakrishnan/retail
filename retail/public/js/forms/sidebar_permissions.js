// Native MultiCheck markup, bulk buttons and normal User Save behavior.
frappe.ui.form.on("User", {
    refresh(frm) {
        const field = frm.fields_dict.retail_sidebar_permissions_html;
        if (!field || frm.doc.user_type !== "System User") return;
        const groups = frappe.boot.retail_sidebar_registry || [];
        const protectedUser = frm.doc.name !== "Administrator" &&
            (frm.doc.roles || []).some(row => row.role === "Super Admin");
        const canManage = Boolean(frappe.boot.can_manage_access ||
            frappe.session.user === "Administrator" ||
            (frappe.user_roles || []).includes("Super Admin"));
        const disabled = !canManage;
        const all = groups.flatMap(group => [group, ...group.children]);
        let selected = new Set(all.map(entry => entry.id));
        if (frm.doc.retail_sidebar_permissions) {
            try { selected = new Set(JSON.parse(frm.doc.retail_sidebar_permissions).allowed || []); }
            catch { selected = new Set(); }
        }
        const wrapper = $(field.wrapper).empty().addClass("retail-sidebar-permissions-editor");
        const commit = () => {
            if (disabled) return;
            control.selected_options = [...selected];
            control.refresh_input();
            updateParents();
            frm.set_value("retail_sidebar_permissions", JSON.stringify({ version: 1, allowed: [...selected].sort() }));
        };
        const updateParents = () => {
            for (const group of groups) {
                control.options.find(option => option.value === group.id).$checkbox.find("input")
                    .prop("indeterminate", false).prop("checked", selected.has(group.id));
            }
        };
        const control = frappe.ui.form.make_control({
            parent: wrapper,
            df: {
                fieldname: "retail_sidebar_permissions", fieldtype: "MultiCheck",
                select_all: true, sort_options: false, columns: 5,
                get_data: () => all.map(entry => ({ label: frappe.utils.escape_html(__(entry.label)),
                    value: entry.id, checked: selected.has(entry.id) })),
                on_change: () => {
                    if (disabled) return;
                    const next = new Set(control.selected_options);
                    const changed = all.find(entry => next.has(entry.id) !== selected.has(entry.id));
                    if (!changed) return;
                    selected = next;
                    const group = groups.find(group => group.id === changed.id);
                    if (group) {
                        for (const child of group.children) {
                            if (selected.has(group.id)) selected.add(child.id);
                            else selected.delete(child.id);
                        }
                    } else {
                        const parent = groups.find(group => group.id === changed.parent);
                        if (parent.children.some(child => selected.has(child.id))) selected.add(parent.id);
                        else selected.delete(parent.id);
                    }
                    commit();
                },
            }, render_input: true,
        });
        control.select_all = (deselect = false) => {
            selected = new Set(deselect ? [] : all.map(entry => entry.id));
            commit();
        };
        const area = control.$checkbox_area.empty().addClass("retail-sidebar-permissions-grid");
        for (const group of groups) {
            const column = $('<div class="retail-sidebar-permissions-group">').appendTo(area);
            control.options.find(option => option.value === group.id).$checkbox
                .addClass("retail-sidebar-permissions-heading").appendTo(column);
            for (const child of group.children) {
                control.options.find(option => option.value === child.id).$checkbox.appendTo(column);
            }
        }
        wrapper.find("input, button").prop("disabled", disabled);
        updateParents();
        if (disabled) $('<p class="text-muted small">')
            .text(__("Sign in as Administrator or an assigned Super Admin to change these selections."))
            .appendTo(wrapper);
        if (protectedUser) $('<p class="text-muted small">').text(__("Celesta Super Administrator retains full access regardless of these selections.")).appendTo(wrapper);
        else if (!frm.doc.retail_sidebar_permissions) $('<p class="text-muted small">')
            .text(__("Existing access is preserved until you change and save this selection. Native roles still control permitted operations."))
            .appendTo(wrapper);
    },
});

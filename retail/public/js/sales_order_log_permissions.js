// Empty native permission rows omit the Set required by Frappe's list indicator.
// Normalize only this restricted log after backend-approved Desk discovery.
(() => {
    const original = frappe.perm.get_role_permissions;
    if (original.retailSalesLogPermissions) return;
    function getPermissions(meta) {
        const permissions = original.apply(this, arguments);
        if (meta.name === "Sales Order API Log" && !meta.permissions?.length &&
            frappe.boot?.user?.can_read?.includes(meta.name)) {
            permissions[0].rights_without_if_owner ||= new Set();
            permissions[0].rights_without_if_owner.add("read");
        }
        return permissions;
    }
    getPermissions.retailSalesLogPermissions = true;
    frappe.perm.get_role_permissions = getPermissions;
})();

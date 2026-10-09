// Use the server-filtered boot snapshot once; customization reloads stay fresh.
(() => {
	function install() {
		const prototype = frappe.views?.Workspace?.prototype;
		if (!prototype?.get_pages || prototype.get_pages.retail_boot_sidebar) return;
		const get_pages = prototype.get_pages;
		let available = true;
		function from_boot() {
			const boot = frappe.boot;
			if (available && boot?.retail_workspace_sidebar_access &&
				Array.isArray(boot.allowed_workspaces)) {
				available = false;
				// Workspace decorates its sidebar rows; keep boot data independent.
				return Promise.resolve({
					...boot.retail_workspace_sidebar_access,
					pages: JSON.parse(JSON.stringify(boot.allowed_workspaces)),
				});
			}
			available = false;
			return get_pages.apply(this, arguments);
		}
		from_boot.retail_boot_sidebar = true;
		prototype.get_pages = from_boot;
	}
	install();
	$(document).on("startup", install);
})();

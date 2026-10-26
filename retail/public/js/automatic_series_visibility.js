// ERPNext's transaction refresh explicitly shows Series on new documents.
// Keep Retail-managed series internal without changing their values or naming.
(() => {
	function install() {
		if (!window.erpnext?.toggle_naming_series || !window.frappe?.boot?.retail_native_code_doctypes || !frappe.ui?.form) {
			setTimeout(install, 150);
			return;
		}
		if (erpnext.toggle_naming_series.__retail_automatic_series) return;
		const managed = new Set(frappe.boot.retail_native_code_doctypes);
		const original = erpnext.toggle_naming_series;
		erpnext.toggle_naming_series = function (...args) {
			const frm = window.cur_frm;
			if (frm && managed.has(frm.doctype) && frm.fields_dict.naming_series) {
				frm.toggle_display("naming_series", false);
				return;
			}
			return original.apply(this, args);
		};
		erpnext.toggle_naming_series.__retail_automatic_series = true;
		for (const doctype of managed) {
			frappe.ui.form.on(doctype, {
				refresh(frm) {
					if (frm.fields_dict.naming_series) frm.toggle_display("naming_series", false);
				},
			});
		}
	}
	install();
})();

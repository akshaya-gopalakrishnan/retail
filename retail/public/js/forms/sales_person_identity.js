frappe.ui.form.on("Sales Person", {
	custom_display_name(frm) {
		// Supply the mandatory native field until the server builds the unique name.
		if (frm.is_new()) {
			frm.set_value("sales_person_name", frm.doc.custom_display_name || "");
		}
	},
});

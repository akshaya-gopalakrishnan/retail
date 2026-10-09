frappe.ui.form.on("External POS Rate Audit", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || !frm.doc.name) {
			return;
		}

		frm.add_custom_button(__("Accept"), () => update_status(frm, "accept"), __("Actions"));
		frm.add_custom_button(__("Ignore"), () => update_status(frm, "ignore"), __("Actions"));
		frm.add_custom_button(__("Recalculate"), () => update_status(frm, "recalculate"), __("Actions"));
	},
});

function update_status(frm, action) {
	frappe.call({
		method: `retail.pos_rate_audit.${action}`,
		args: { name: frm.doc.name },
		callback() {
			frm.reload_doc();
		},
	});
}

(() => {
	const admin = () => frappe.session.user === "Administrator" || frappe.user.has_role("Super Admin");
	for (const doctype of ["POS Sync Log", "POS Accepted Transaction", "POS Settlement Allocation", "POS Settlement Exception"]) {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				const allowed = admin() && !frm.is_new();
				const payload = doctype === "POS Sync Log" ? "request_json" : "correction_payload_json";
				frm.set_df_property(payload, "read_only", !allowed);
				frm.set_df_property("correction_reason", "read_only", !allowed);
				if (doctype === "POS Sync Log") {
					for (const field of frm.meta.fields) {
						if (![payload, "correction_reason"].includes(field.fieldname)) {
							frm.set_df_property(field.fieldname, "read_only", true);
						}
					}
				}
				if (!allowed) return;
				if (doctype === "POS Sync Log" && !["POS Sale", "Sales Invoice", "Credit Sales Invoice", "POS Return", "Return"].includes(frm.doc.sync_type)) return;
				frm.add_custom_button(__("Post / Retry"), async () => {
					if (frm.is_dirty()) await frm.save();
					if (frm.is_dirty()) return;
					const response = await frappe.call({
						method: "retail.pos_admin_recovery.retry_posting",
						args: {doctype, name: frm.doc.name}, freeze: true,
						freeze_message: __("Posting POS transaction..."),
					});
					await frm.reload_doc();
					const result = response.message || {};
					frappe.msgprint({title: __("Posting Result"),
						message: frappe.utils.escape_html(result.error || result.status || result.settlement_status || "Completed"),
						indicator: result.error || result.status === "Reconciliation Exception" ? "orange" : "green"});
				});
			},
		});
	}
})();

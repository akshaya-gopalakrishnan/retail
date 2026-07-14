(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Retail Item Rate Audit", {
		refresh(frm) {
			if (frm.doc.action !== "Update" || frm.doc.status === "Reversed") return;
			frm.add_custom_button(__("Reverse This Update"), () => reverseAudit(frm), __("Retail"));
		},
	});

	function reverseAudit(frm) {
		frappe.confirm(
			__("Restore Item {0} {1} rate from {2} back to {3}? This affects future pricing only and will not change submitted documents.", [
				frm.doc.item,
				frm.doc.direction,
				format_currency(frm.doc.new_net_rate),
				format_currency(frm.doc.old_net_rate),
			]),
			async () => {
				const result = await frappe.call({
					method: "retail.domains.item.rate_audit.reverse_rate_audit",
					args: { audit_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Reversing Item Rate"),
				});
				frappe.show_alert({ message: __("Rate reversed: {0}", [result.message]), indicator: "green" });
				frm.reload_doc();
			}
		);
	}
})();

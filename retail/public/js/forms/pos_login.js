(function () {
	function setup_pos_pin(frm) {
		const field = frm.fields_dict.pos_quick_pin;
		if (!field || !field.$input) return;

		field.$input
			.attr("maxlength", "4")
			.attr("inputmode", "numeric")
			.attr("pattern", "[0-9]*")
			.attr("autocomplete", "off")
			.attr("type", "password")
			.attr("placeholder", frm.doc.pos_quick_pin_hash ? "PIN configured" : "");

		field.$input.off("input.pos_pin").on("input.pos_pin", function () {
			const value = String(this.value || "").replace(/\D/g, "").slice(0, 4);
			if (this.value !== value) {
				this.value = value;
				frm.set_value("pos_quick_pin", value);
			}
		});
	}

	async function show_privileges(frm) {
		frm.set_df_property("pos_operator_privilege", "read_only", !frappe.user.has_role("System Manager"));
		frm.set_query("pos_operator_privilege", () => ({ filters: { disabled: 0 } }));
		const field = frm.fields_dict.pos_privileges_preview;
		if (!field) return;
		field.$wrapper.empty();
		if (frm.is_new()) {
			field.$wrapper.text(__("Save the employee to preview POS privileges."));
			return;
		}
		const profile = frm.doc.pos_operator_privilege;
		const { message } = await frappe.call({
			method: "retail.pos_privileges.get_privilege_preview",
			args: { employee: frm.doc.name, profile_name: profile || null },
		});
		if (profile !== frm.doc.pos_operator_privilege) return;
		const allowed = (message || []).filter(row => row.allowed);
		field.$wrapper.html(allowed.length
			? `<p class="text-muted">${__("Allowed actions from the selected profile:")}</p><ul style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px 24px">${allowed.map(row => `<li>${frappe.utils.escape_html(__(row.label))}</li>`).join("")}</ul>`
			: `<p class="text-muted">${__("No POS actions allowed.")}</p>`);
	}

	frappe.ui.form.on("Employee", {
		refresh(frm) { setup_pos_pin(frm); show_privileges(frm); },
		pos_operator_privilege: show_privileges,
		pos_quick_pin: setup_pos_pin,
	});

	frappe.ui.form.on("User", {
		refresh: setup_pos_pin,
		pos_quick_pin: setup_pos_pin,
	});
})();

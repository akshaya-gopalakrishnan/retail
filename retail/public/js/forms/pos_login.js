(function () {
	function setup_pos_pin(frm) {
		const field = frm.fields_dict.pos_quick_pin;
		if (!field || !field.$input) return;

		field.$input
			.attr("maxlength", "4")
			.attr("inputmode", "numeric")
			.attr("pattern", "[0-9]*")
			.attr("autocomplete", "off")
			.attr("type", "password");

		field.$input.off("input.pos_pin").on("input.pos_pin", function () {
			const value = String(this.value || "").replace(/\D/g, "").slice(0, 4);
			if (this.value !== value) {
				this.value = value;
				frm.set_value("pos_quick_pin", value);
			}
		});
	}

	frappe.ui.form.on("Employee", {
		refresh: setup_pos_pin,
		pos_quick_pin: setup_pos_pin,
	});

	frappe.ui.form.on("User", {
		refresh: setup_pos_pin,
		pos_quick_pin: setup_pos_pin,
	});
})();

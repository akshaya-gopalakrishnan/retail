// Expand Address Line 1 in full forms and Customer/Supplier Quick Entry.
(() => {
	class AddressLine extends frappe.ui.form.ControlSmallText {
		make_input() {
			super.make_input();
			const input = this.$input[0];
			const resize = () => {
				input.style.height = "auto";
				input.style.height = `${Math.max(38, input.scrollHeight + 2)}px`;
			};
			this.$input.css({ "min-height": "38px", height: "38px", overflow: "hidden", resize: "none" })
				.on("input.retail_address_growth", resize);
			new ResizeObserver(resize).observe(input);
			requestAnimationFrame(resize);
		}
		set_formatted_input(value) {
			super.set_formatted_input(value);
			this.$input?.trigger("input.retail_address_growth");
		}
	}
	const make_control = frappe.ui.form.make_control;
	frappe.ui.form.make_control = function (options) {
		if (options.df?.fieldname !== "address_line1") return make_control.call(this, options);
		return new AddressLine({ ...options, df: { ...options.df, fieldtype: "Small Text" } });
	};
})();

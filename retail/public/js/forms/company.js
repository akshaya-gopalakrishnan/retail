(function () {
	if (!window.frappe?.ui?.form) return;

	const BILL_FIELDS = [
		"custom_bill_address", "custom_bill_phone", "custom_bill_email", "custom_bill_tax_id",
		...Array.from({ length: 5 }, (_, index) => `custom_bill_h${index + 1}`),
		...Array.from({ length: 5 }, (_, index) => `custom_bill_f${index + 1}`),
	];

	function resize(input) {
		if (!input?.getClientRects().length) return;
		input.style.height = "0px";
		const style = getComputedStyle(input);
		const border = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
		input.style.height = Math.max(32, input.scrollHeight + border) + "px";
	}

	function setupBillFields(frm) {
		frm._retail_bill_resize_observer?.disconnect();
		const widths = new WeakMap();
		frm._retail_bill_resize_observer = new ResizeObserver((entries) => {
			for (const { target, contentRect } of entries) {
				if (widths.get(target) === contentRect.width) continue;
				widths.set(target, contentRect.width);
				requestAnimationFrame(() => resize(target));
			}
		});

		for (const fieldname of BILL_FIELDS) {
			let field = frm.fields_dict[fieldname];
			if (!field || !["Data", "Small Text", "Text", "Long Text"].includes(field.df.fieldtype)) continue;

			if (field.df.fieldtype === "Data" && !(field instanceof frappe.ui.form.ControlSmallText)) {
				// Use a native textarea while retaining the stored Data field's validation and length.
				const df = field.df;
				frm.layout.replace_field(fieldname, { ...df, fieldtype: "Small Text" });
				field = frm.fields_dict[fieldname];
				field.df = df;
				field.docname = frm.doc.name;
				field.refresh();
				if (field.$input) field.set_input_attributes();
			}

			const input = field.$input;
			if (!input?.is("textarea")) continue;
			input.attr("rows", 1).css({
				"min-height": "32px", "max-height": "none", "overflow-y": "hidden",
				"overflow-wrap": "anywhere", resize: "none",
			});
			input.off("input.retail-bill-format").on("input.retail-bill-format", () => resize(input[0]));
			frm._retail_bill_resize_observer.observe(input[0]);
			requestAnimationFrame(() => resize(input[0]));
		}
	}

	const handlers = { refresh: setupBillFields, onload_post_render: setupBillFields };
	for (const fieldname of BILL_FIELDS) {
		handlers[fieldname] = (frm) => requestAnimationFrame(() => resize(frm.fields_dict[fieldname]?.$input?.[0]));
	}
	frappe.ui.form.on("Company", handlers);
})();

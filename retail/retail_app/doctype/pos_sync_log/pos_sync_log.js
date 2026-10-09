frappe.ui.form.on("POS Sync Log", {
	setup(frm) {
		for (const fieldname of ["request_json", "response_json"]) {
			const control = frm.fields_dict[fieldname];
			const set_formatted_input = control.set_formatted_input;
			// Format only the editor: operation receipts compare the stored JSON exactly.
			control.set_formatted_input = function (value) {
				let formatted = value;
				try {
					if (value) formatted = JSON.stringify(JSON.parse(value), null, 2);
				} catch {
					// Keep incomplete or non-JSON payloads visible as received.
				}
				return set_formatted_input.call(this, formatted);
			};
		}
	},
});

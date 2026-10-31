frappe.ui.form.on("POS Sync Log", {
	refresh(frm) {
		if (frm.is_new()) return;
		for (const [label, doctype] of [
			["Settlement Exception", "POS Settlement Exception"],
			["Rate Audit", "External POS Rate Audit"],
		]) {
			frm.add_custom_button(__(label), async () => {
				if (!frm.doc.external_reference) {
					frappe.msgprint(__("This log has no external POS reference."));
					return;
				}
				const filters = { external_pos_reference: frm.doc.external_reference };
				const rows = await frappe.db.get_list(doctype, {
					filters, fields: ["name"], limit: 2,
				});
				if (rows.length === 1) {
					frappe.set_route("Form", doctype, rows[0].name);
				} else if (rows.length > 1) {
					frappe.route_options = filters;
					frappe.set_route("List", doctype);
				} else {
					frappe.msgprint(__("No {0} records were found for this log.", [__(label)]));
				}
			});
		}
	},
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
			const refresh_input = control.refresh_input;
			control.refresh_input = function () {
				refresh_input.call(this);
				if (this.disp_status === "None") return;
				// Keep read-only receipts in the same JSON viewer as editable requests.
				const read_only = !this.can_write();
				if (read_only) {
					$(this.disp_area).hide();
					$(this.input_area).show();
					this.make_input();
				}
				this.set_formatted_input(this.value).then(() => {
					if (!this.editor) return;
					this.editor.setReadOnly(read_only);
					this.ace_editor_target.css("pointer-events", "");
					this.editor.resize();
				});
			};
		}
	},
});

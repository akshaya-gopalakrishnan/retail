frappe.ui.form.on("Van Fleet", {
	async vehicle_status(frm) {
		if (frm.is_new() || !["Inactive", "Maintenance"].includes(frm.doc.vehicle_status)) return;
		const requested_status = frm.doc.vehicle_status;
		const { message: sessions } = await frm.call("get_open_sessions");
		if (!sessions?.length || frm.doc.vehicle_status !== requested_status) return;
		// Keep the requested value visible; server validation also blocks Save.
		frappe.msgprint({
			title: __("Open Van Session"),
			indicator: "orange",
			message: __("Close the open Van Session(s) {0} before setting Vehicle Status to {1}.", [
				sessions.map((name) => frappe.utils.get_form_link("Van Session", name, true)).join(", "),
				frappe.utils.escape_html(requested_status),
			]),
			primary_action: {
				label: __("Open Session"),
				action() {
					frappe.hide_msgprint();
					frappe.set_route("Form", "Van Session", sessions[0]);
				},
			},
		});
	},
	refresh(frm) {
		const input = frm.fields_dict.remarks?.$input?.[0];
		if (!input) return;
		const resize = () => {
			const height = frm.fields_dict.vehicle_status?.$input?.outerHeight() || 32;
			input.style.minHeight = `${height}px`;
			input.style.height = `${height}px`;
			input.style.overflowY = "hidden";
			input.style.resize = "none";
			const style = getComputedStyle(input);
			const border = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
			input.style.height = `${Math.max(height, input.scrollHeight + border)}px`;
		};
		$(input).off("input.vanFleetRemarks").on("input.vanFleetRemarks", resize);
		if (frm.__van_remarks_observer) frm.__van_remarks_observer.disconnect();
		frm.__van_remarks_observer = new ResizeObserver(resize);
		frm.__van_remarks_observer.observe(input.parentElement);
		requestAnimationFrame(resize);
	},
});

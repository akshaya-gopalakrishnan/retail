for (const [doctype, field, active_value] of [
	["POS Profile", "disabled", 0],
	["POS Branch Counter", "is_active", 1],
]) {
	const settings = frappe.listview_settings[doctype] ||= {};
	settings.add_fields = [...new Set([...(settings.add_fields || []), field])];
	settings.get_indicator = (doc) => {
		const active = Number(doc[field]) === active_value;
		return [__(active ? "Active" : "Inactive"), active ? "green" : "red",
			`${field},=,${active ? active_value : 1 - active_value}`];
	};
}

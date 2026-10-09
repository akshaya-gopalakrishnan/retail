(function () {
	frappe.listview_settings["Van Session"] = {
		add_fields: ["status"],
		get_indicator(doc) {
			const status = doc.status || "Draft";
			const colors = {
				Draft: "gray",
				Open: "green",
				Closed: "orange",
				Cancelled: "red",
			};

			return [__(status), colors[status] || "gray", `status,=,${status}`];
		},
	};
})();

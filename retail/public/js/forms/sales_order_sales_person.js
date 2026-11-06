frappe.ui.form.on("Sales Order", {
	setup(frm) {
		frm.set_query("sales_person_id", () => ({
			query: "retail.sales_order_sales_person.search_sales_people",
		}));
	},
	async sales_person_id(frm) {
		const code = frm.doc.sales_person_id;
		if (!code) {
			await frm.set_value("sales_person_name", "");
			return;
		}
		const { message } = await frappe.db.get_value("Sales Person",
			{ custom_document_code: code }, ["custom_display_name", "sales_person_name"]);
		if (frm.doc.sales_person_id === code) {
			await frm.set_value("sales_person_name",
				message?.custom_display_name || message?.sales_person_name || "");
		}
	},
});

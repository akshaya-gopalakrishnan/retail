(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Payment Entry", {
		onload(frm) {
			applyVanInvoiceContext(frm);
		},
		refresh(frm) {
			applyVanInvoiceContext(frm);
		},
		custom_van_session(frm) {
			fetchVanSessionDetails(frm);
		},
	});

	function applyVanInvoiceContext(frm) {
		const invoiceName = getReferencedSalesInvoice(frm);
		if (!invoiceName) return;

		frappe.db.get_value(
			"Sales Invoice",
			invoiceName,
			["custom_is_van_sale", "custom_van_session"]
		).then((response) => {
			const invoice = response.message || {};
			if (cint(invoice.custom_is_van_sale) !== 1) return;

			const values = { custom_is_van_payment: 1 };
			if (invoice.custom_van_session) {
				values.custom_van_session = invoice.custom_van_session;
			}

			frm.set_value(values).then(() => fetchVanSessionDetails(frm));
		});
	}

	function getReferencedSalesInvoice(frm) {
		const routeOptions = frappe.route_options || {};
		if (routeOptions.reference_doctype === "Sales Invoice" && routeOptions.reference_name) {
			return routeOptions.reference_name;
		}

		const reference = (frm.doc.references || []).find((row) => {
			return row.reference_doctype === "Sales Invoice" && row.reference_name;
		});
		return reference?.reference_name;
	}

	function fetchVanSessionDetails(frm) {
		if (cint(frm.doc.custom_is_van_payment) !== 1 || !frm.doc.custom_van_session) return;

		frappe.db.get_value(
			"Van Session",
			frm.doc.custom_van_session,
			["van", "driver", "driver_name"]
		).then((response) => {
			const session = response.message || {};
			const values = {};

			if (session.van) values.custom_van = session.van;
			if (session.driver) values.custom_driver = session.driver;
			if (session.driver_name) values.custom_driver_name = session.driver_name;

			if (Object.keys(values).length) {
				frm.set_value(values);
			}
		});
	}
})();

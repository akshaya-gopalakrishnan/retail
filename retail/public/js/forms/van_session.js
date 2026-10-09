(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Van Session", {
		refresh(frm) {
			const operator = frappe.user.has_role("Van Sales User") &&
				!frappe.user.has_role("Van Sales Manager") && !frappe.user.has_role("System Manager");
			["custom_salesperson", "van", "driver", "session_date"].forEach(field => {
				frm.set_df_property(field, "read_only", operator ? 1 : 0);
			});
			toggleClosingFields(frm);
			addVanStockEntryButton(frm);
		},
		status(frm) {
			toggleClosingFields(frm);
		},
		validate(frm) {
			validateClosingValues(frm);
		},
	});

	function toggleClosingFields(frm) {
		const canEditClosing = frm.doc.status === "Closed" && frm.doc.docstatus !== 2;
		["closing_cash", "closing_km", "close_time"].forEach(field => {
			frm.set_df_property(field, "read_only", canEditClosing ? 0 : 1);
		});
	}

	function validateClosingValues(frm) {
		if (flt(frm.doc.opening_cash) < 0) {
			frappe.validated = false;
			frappe.throw(__("Opening Cash cannot be negative."));
		}

		if (frm.doc.closing_cash !== undefined && frm.doc.closing_cash !== null && flt(frm.doc.closing_cash) < 0) {
			frappe.validated = false;
			frappe.throw(__("Closing Cash cannot be negative."));
		}

		if (frm.doc.status !== "Closed") return;

		if (frm.doc.closing_cash === undefined || frm.doc.closing_cash === null) {
			frappe.validated = false;
			frappe.throw(__("Closing Cash is required to close a Van Session."));
		}

		const hasOpeningKm = frm.doc.opening_km !== undefined && frm.doc.opening_km !== null && frm.doc.opening_km !== "";
		const hasClosingKm = frm.doc.closing_km !== undefined && frm.doc.closing_km !== null && frm.doc.closing_km !== "";
		if (hasOpeningKm && hasClosingKm && flt(frm.doc.closing_km) < flt(frm.doc.opening_km)) {
			frappe.validated = false;
			frappe.throw(__("Closing KM cannot be less than Opening KM."));
		}
	}

	function addVanStockEntryButton(frm) {
		if (frm.doc.__islocal || frm.doc.status !== "Open") return;
		if (!canUseVanStockEntry()) return;

		frm.add_custom_button(
			__("Van Stock Entry"),
			() => createVanStockEntry(frm),
			__("Create")
		);
	}

	function canUseVanStockEntry() {
		return ["Van Sales User", "Van Sales Manager", "System Manager"].some((role) =>
			frappe.user_roles?.includes(role)
		);
	}

	function createVanStockEntry(frm) {
		frappe.route_options = {
			custom_is_van_stock_entry: 1,
			custom_van_session: frm.doc.name,
			custom_van: frm.doc.van,
			custom_van_warehouse: frm.doc.van_warehouse,
			custom_driver: frm.doc.driver,
			custom_driver_name_: frm.doc.driver_name,
			stock_entry_type: "Material Transfer",
			custom_van_stock_entry_type: "Loading",
		};
		frappe.new_doc("Stock Entry");
	}
})();

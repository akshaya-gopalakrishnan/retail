(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Material Request", {
		onload(frm) {
			applyVanStockRequestState(frm);
		},
		refresh(frm) {
			applyVanStockRequestState(frm);
		},
		custom_is_van_stock_request(frm) {
			applyVanStockRequestState(frm);
		},
		custom_van_session(frm) {
			fetchVanSessionDetails(frm);
		},
		custom_van_warehouse(frm) {
			applyVanWarehouseToItems(frm, true);
		},
	});

	frappe.ui.form.on("Material Request Item", {
		item_code(frm, cdt, cdn) {
			const row = locals[cdt]?.[cdn];
			if (isVanStockRequest(frm) && row?.item_code && !row.warehouse) {
				applyVanWarehouseToRow(frm, cdt, cdn);
			}
		},
	});

	function isVanStockRequest(frm) {
		return cint(frm.doc?.custom_is_van_stock_request) === 1;
	}

	function canUseVanStockRequest() {
		return ["Van Sales User", "Van Sales Manager", "System Manager"].some((role) =>
			frappe.user_roles?.includes(role)
		);
	}

	function applyVanStockRequestState(frm) {
		if (!canUseVanStockRequest()) {
			hideVanStockRequestFields(frm);
			return;
		}

		const isVan = isVanStockRequest(frm);
		toggleVanStockRequestFields(frm, isVan);
		if (!isVan) return;

		if (frm.doc.material_request_type !== "Material Transfer") {
			frm.set_value("material_request_type", "Material Transfer");
		}

		if (!frm.doc.custom_van_request_type) {
			frm.set_value("custom_van_request_type", "Loading");
		}

		setVanSessionControlledFieldsReadonly(frm);
		setItemWarehouseEditable(frm);
		setVanSessionQuery(frm);
		autofillOpenVanSession(frm);
		applyVanWarehouseToItems(frm, false);
	}

	function hideVanStockRequestFields(frm) {
		[
			"custom_van_stock_request_section",
			"custom_is_van_stock_request",
			"custom_van_request_type",
			"custom_van_session",
			"custom_van",
			"custom_van_warehouse",
			"custom_driver",
			"custom_driver_name",
		].forEach((fieldname) => {
			if (frm.fields_dict[fieldname]) {
				frm.set_df_property(fieldname, "hidden", 1);
			}
		});
	}

	function toggleVanStockRequestFields(frm, isVan) {
		if (frm.fields_dict.custom_is_van_stock_request) {
			frm.set_df_property("custom_is_van_stock_request", "hidden", 1);
		}

		if (frm.fields_dict.custom_van_stock_request_section) {
			frm.set_df_property("custom_van_stock_request_section", "hidden", isVan ? 0 : 1);
		}

		[
			"custom_van_request_type",
			"custom_van_session",
			"custom_van",
			"custom_van_warehouse",
			"custom_driver",
			"custom_driver_name",
		].forEach((fieldname) => {
			if (frm.fields_dict[fieldname]) {
				frm.set_df_property(fieldname, "hidden", isVan ? 0 : 1);
			}
		});

		["custom_van_request_type", "custom_van_session"].forEach((fieldname) => {
			if (frm.fields_dict[fieldname]) {
				frm.set_df_property(fieldname, "reqd", isVan ? 1 : 0);
			}
		});
	}

	function fetchVanSessionDetails(frm) {
		if (!isVanStockRequest(frm) || !frm.doc.custom_van_session) return;

		frappe.db.get_value(
			"Van Session",
			frm.doc.custom_van_session,
			["van", "van_warehouse", "driver", "driver_name"]
		).then((response) => {
			const session = response.message || {};
			const values = {};

			if (session.van) values.custom_van = session.van;
			if (session.van_warehouse) values.custom_van_warehouse = session.van_warehouse;
			if (session.driver) values.custom_driver = session.driver;
			if (session.driver_name) values.custom_driver_name = session.driver_name;

			if (Object.keys(values).length) {
				frm.set_value(values).then(() => {
					applyVanWarehouseToItems(frm, true);
				});
			}
		});
	}

	function setVanSessionQuery(frm) {
		if (!frm.fields_dict.custom_van_session) return;

		frm.set_query("custom_van_session", () => ({
			filters: {
				status: "Open",
			},
		}));
	}

	function autofillOpenVanSession(frm) {
		if (!frm.doc.__islocal || frm.doc.custom_van_session || frm.__van_session_autofill_done) return;
		frm.__van_session_autofill_done = true;

		frappe.db.get_list("Van Session", {
			filters: { status: "Open" },
			fields: ["name"],
			limit: 2,
			order_by: "session_date desc, modified desc",
		}).then((sessions) => {
			if (!isVanStockRequest(frm) || frm.doc.custom_van_session) return;
			if ((sessions || []).length !== 1) return;

			frm.set_value("custom_van_session", sessions[0].name).then(() => {
				fetchVanSessionDetails(frm);
			});
		});
	}

	function setVanSessionControlledFieldsReadonly(frm) {
		[
			"custom_van",
			"custom_van_warehouse",
			"custom_driver",
			"custom_driver_name",
		].forEach((fieldname) => {
			if (frm.fields_dict[fieldname]) {
				frm.set_df_property(fieldname, "read_only", 1);
			}
		});
	}

	function setItemWarehouseEditable(frm) {
		frm.fields_dict.items?.grid?.update_docfield_property("warehouse", "read_only", 0);
	}

	function applyVanWarehouseToItems(frm, overwrite) {
		if (!isVanStockRequest(frm) || !frm.doc.custom_van_warehouse) return;

		(frm.doc.items || []).forEach((row) => {
			if (!row.item_code) return;
			if (!overwrite && row.warehouse) return;
			frappe.model.set_value(row.doctype, row.name, "warehouse", frm.doc.custom_van_warehouse);
		});
		frm.refresh_field("items");
	}

	function applyVanWarehouseToRow(frm, cdt, cdn) {
		if (!frm.doc.custom_van_warehouse) return;
		frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.custom_van_warehouse);
	}
})();

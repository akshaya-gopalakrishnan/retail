(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Stock Entry", {
		refresh(frm) {
			applyVanStockEntryState(frm);
			renderVanWarehouseStockPanel(frm);
		},
		onload(frm) {
			applyVanStockEntryState(frm);
		},
		custom_is_van_stock_entry(frm) {
			applyVanStockEntryState(frm);
			renderVanWarehouseStockPanel(frm);
		},
		custom_van_session(frm) {
			fetchVanSessionDetails(frm);
		},
		custom_van_warehouse(frm) {
			renderVanWarehouseStockPanel(frm);
			autofillOffloadingItems(frm);
		},
		custom_van_stock_entry_type(frm) {
			renderVanWarehouseStockPanel(frm);
			autofillOffloadingItems(frm);
		},
	});

	function isVanStockEntry(frm) {
		return cint(frm.doc.custom_is_van_stock_entry) === 1;
	}

	function canUseVanStockEntry() {
		return ["Van Sales User", "Van Sales Manager", "System Manager"].some((role) =>
			frappe.user_roles?.includes(role)
		);
	}

	function applyVanStockEntryState(frm) {
		if (!canUseVanStockEntry()) {
			hideAllVanStockFields(frm);
			return;
		}

		const isVan = isVanStockEntry(frm);
		toggleVanStockFields(frm, isVan);

		if (isVan && frm.doc.stock_entry_type !== "Material Transfer") {
			frm.set_value("stock_entry_type", "Material Transfer");
		}

		if (isVan && !frm.doc.custom_van_stock_entry_type) {
			frm.set_value("custom_van_stock_entry_type", "Loading");
		}

		autofillOffloadingItems(frm);
	}

	function hideAllVanStockFields(frm) {
		[
			"custom_is_van_stock_entry",
			"custom_van_session",
			"custom_van",
			"custom_van_stock_entry_type",
			"custom_van_warehouse",
			"custom_driver",
			"custom_driver_name_",
			"custom_van_warehouse_stock",
		].forEach((fieldname) => {
			if (frm.fields_dict[fieldname]) {
				frm.set_df_property(fieldname, "hidden", 1);
			}
		});

		frm.fields_dict.custom_van_warehouse_stock?.$wrapper.empty();
	}

	function toggleVanStockFields(frm, isVan) {
		if (frm.fields_dict.custom_is_van_stock_entry) {
			frm.set_df_property("custom_is_van_stock_entry", "hidden", 0);
		}

		[
			"custom_van_session",
			"custom_van",
			"custom_van_stock_entry_type",
			"custom_van_warehouse",
			"custom_driver",
			"custom_driver_name_",
			"custom_van_warehouse_stock",
		].forEach((fieldname) => {
			if (frm.fields_dict[fieldname]) {
				frm.set_df_property(fieldname, "hidden", isVan ? 0 : 1);
			}
		});
	}

	function renderVanWarehouseStockPanel(frm, rows) {
		const field = frm.fields_dict.custom_van_warehouse_stock;
		if (!field) return;

		if (!canUseVanStockEntry() || !isVanStockEntry(frm)) {
			field.$wrapper.empty();
			return;
		}

		const hasWarehouse = Boolean(frm.doc.custom_van_warehouse);
		const stockRows = rows || [];

		field.$wrapper.html(`
			<div class="van-stock-readonly-panel">
				<div class="van-stock-action-row">
					<button class="btn btn-primary btn-sm van-fetch-stock-btn" type="button" ${hasWarehouse ? "" : "disabled"}>
						${__("Fetch Van Warehouse Stock")}
					</button>
				</div>
				${stockRows.length ? renderReadonlyTable(stockRows) : renderEmptyState(hasWarehouse)}
			</div>
		`);

		field.$wrapper.find(".van-fetch-stock-btn").on("click", () => fetchVanWarehouseStock(frm));
	}

	function renderEmptyState(hasWarehouse) {
		if (!hasWarehouse) return "";
		return "";
	}

	function renderReadonlyTable(rows) {
		const tableRows = rows.map((row, index) => `
			<tr>
				<td class="text-center">${index + 1}</td>
				<td>${frappe.utils.escape_html(row.warehouse || "")}</td>
				<td>${frappe.utils.escape_html(row.item_name || "")}</td>
				<td>${frappe.utils.escape_html(row.item_code || "")}</td>
				<td class="text-right">${frappe.format(row.actual_qty || 0, { fieldtype: "Float" })}</td>
				<td>${frappe.utils.escape_html(row.stock_uom || "")}</td>
				<td class="text-right">${frappe.format(row.valuation_rate || 0, { fieldtype: "Currency" })}</td>
			</tr>
		`).join("");

		return `
			<div class="van-stock-readonly-table table-responsive">
				<table class="table table-bordered table-sm">
					<thead>
						<tr>
							<th class="text-center">${__("No.")}</th>
							<th>${__("Warehouse")}</th>
							<th>${__("Item Name")}</th>
							<th>${__("Item Code")}</th>
							<th class="text-right">${__("Actual Qty")}</th>
							<th>${__("UOM")}</th>
							<th class="text-right">${__("Basic Rate")}</th>
						</tr>
					</thead>
					<tbody>${tableRows}</tbody>
				</table>
			</div>
		`;
	}

	function fetchVanWarehouseStock(frm) {
		if (!frm.doc.custom_van_warehouse) {
			frappe.msgprint(__("Please select Van Warehouse first."));
			return;
		}

		frappe.call({
			method: "retail.van_stock.get_van_warehouse_stock",
			args: {
				warehouse: frm.doc.custom_van_warehouse,
			},
			freeze: true,
			freeze_message: __("Fetching van warehouse stock..."),
		}).then((response) => {
			renderVanWarehouseStockPanel(frm, response.message || []);
		});
	}

	function isOffloading(frm) {
		return isVanStockEntry(frm) && frm.doc.custom_van_stock_entry_type === "Offloading";
	}

	function autofillOffloadingItems(frm) {
		if (!frm.doc.__islocal || frm.__van_offloading_autofill_done) return;
		if (!isOffloading(frm) || !frm.doc.custom_van_warehouse) return;
		if ((frm.doc.items || []).some((row) => row.item_code)) return;

		frm.__van_offloading_autofill_done = true;
		loadOffloadingItems(frm, false);
	}

	function loadOffloadingItems(frm, force) {
		if (!isOffloading(frm)) return;
		if (!frm.doc.custom_van_warehouse) {
			frappe.msgprint(__("Please select Van Warehouse first."));
			return;
		}

		const hasItems = (frm.doc.items || []).some((row) => row.item_code);
		if (hasItems && !force) return;

		if (hasItems && force) {
			frappe.confirm(
				__("This will replace the current item rows with the Van Warehouse balance. Continue?"),
				() => fetchAndSetOffloadingItems(frm)
			);
			return;
		}

		fetchAndSetOffloadingItems(frm);
	}

	function fetchAndSetOffloadingItems(frm) {
		frappe.call({
			method: "retail.van_stock.get_van_warehouse_stock",
			args: {
				warehouse: frm.doc.custom_van_warehouse,
			},
			freeze: true,
			freeze_message: __("Loading offloading items..."),
		}).then((response) => {
			const rows = response.message || [];
			setOffloadingItems(frm, rows);
			renderVanWarehouseStockPanel(frm, rows);
		});
	}

	function setOffloadingItems(frm, stockRows) {
		frappe.model.clear_table(frm.doc, "items");

		stockRows.forEach((stockRow) => {
			const qty = flt(stockRow.actual_qty);
			if (!stockRow.item_code || qty <= 0) return;

			const row = frm.add_child("items");
			row.item_code = stockRow.item_code;
			row.item_name = stockRow.item_name;
			row.uom = stockRow.stock_uom;
			row.stock_uom = stockRow.stock_uom;
			row.conversion_factor = 1;
			row.qty = qty;
			row.transfer_qty = qty;
			row.s_warehouse = frm.doc.custom_van_warehouse;
		});

		frm.refresh_field("items");
	}

	function fetchVanSessionDetails(frm) {
		if (!isVanStockEntry(frm) || !frm.doc.custom_van_session) return;

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
			if (session.driver_name) values.custom_driver_name_ = session.driver_name;

			if (Object.keys(values).length) {
				frm.set_value(values).then(() => renderVanWarehouseStockPanel(frm));
			}
		});
	}
})();

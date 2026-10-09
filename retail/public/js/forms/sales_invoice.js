(function () {
	if (!window.frappe?.ui?.form) return;

		frappe.ui.form.on("Sales Invoice", {
			onload_post_render(frm) {
				keepCompanyVisible(frm);
				applyVanSalesInvoiceState(frm);
				populateSalesPersonField(frm);
			},
			refresh(frm) {
				keepCompanyVisible(frm);
				applyVanSalesInvoiceState(frm);
				populateSalesPersonField(frm);
				restoreStandardDraftAction(frm);
			},
			custom_is_van_sale(frm) {
				applyVanSalesInvoiceState(frm);
			},
			custom_van_session(frm) {
				fetchVanSessionDetails(frm);
			},
			custom_van_warehouse(frm) {
				applyVanWarehouseToItems(frm);
			},
			custom_retail_sales_person(frm) {
				syncSalesPersonToSalesTeam(frm);
			},
			sales_team_add(frm, cdt, cdn) {
				populateSalesPersonField(frm);
			},
			after_save(frm) {
				restoreStandardDraftAction(frm, true);
			},
		});

	function keepCompanyVisible(frm) {
		if (!frm?.fields_dict?.company) return;

		const showCompany = () => {
			if (!frm.fields_dict.company) return;
			frm.set_df_property("company", "hidden", 0);
			frm.fields_dict.company.df.hidden = 0;
			frm.toggle_display("company", true);
			frm.refresh_field("company");
		};

		showCompany();
		frappe.after_ajax(showCompany);
		setTimeout(showCompany, 0);
		setTimeout(showCompany, 250);
	}

	function restoreStandardDraftAction(frm, forceClean = false) {
		if (!frm || cint(frm.doc?.docstatus) !== 0 || frm.doc?.__islocal) return;

		const savedAt = Date.now();
		[100, 500, 1200, 2500].forEach((delay) => {
			setTimeout(() => {
				if (!frm || cint(frm.doc?.docstatus) !== 0 || frm.doc?.__islocal) return;
				if (frm.__retail_local_draft_last_user_event_at > savedAt) return;

				if (forceClean) {
					frm.doc.__unsaved = 0;
				}
				if (!frm.doc.__unsaved) {
					frm.toolbar?.set_primary_action?.(false);
					frm.toolbar?.show_title_as_dirty?.();
				}
			}, delay);
			});
		}

		function isVanSalesInvoice(frm) {
			return cint(frm.doc?.custom_is_van_sale) === 1;
		}

			function applyVanSalesInvoiceState(frm) {
				if (!isVanSalesInvoice(frm)) return;

				setVanSessionControlledFieldsReadonly(frm);

				if (frm.doc.update_stock !== 1) {
					frm.set_value("update_stock", 1);
				}
				applyVanWarehouseToItems(frm);
			}

			function populateSalesPersonField(frm) {
				if (!frm.doc.custom_retail_sales_person && frm.doc.sales_team?.length) {
					frm.set_value("custom_retail_sales_person", frm.doc.sales_team[0].sales_person);
				}
			}

			function syncSalesPersonToSalesTeam(frm) {
				const salesPerson = frm.doc.custom_retail_sales_person;
				if (!salesPerson) return;

				const salesTeam = frm.doc.sales_team || [];
				if (salesTeam.length) {
					if (salesTeam[0].sales_person !== salesPerson) {
						frappe.model.set_value(salesTeam[0].doctype, salesTeam[0].name, "sales_person", salesPerson);
					}
					if (salesTeam.length === 1 && flt(salesTeam[0].allocated_percentage) !== 100) {
						frappe.model.set_value(
							salesTeam[0].doctype,
							salesTeam[0].name,
							"allocated_percentage",
							100
						);
					}
					return;
				}

				const row = frm.add_child("sales_team");
			frappe.model.set_value(row.doctype, row.name, {
				 sales_person: salesPerson,
				 allocated_percentage: 100,
			});
				frm.refresh_field("sales_team");
			}

		function fetchVanSessionDetails(frm) {
			if (!isVanSalesInvoice(frm) || !frm.doc.custom_van_session) return;

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
						frm.set_value(values).then(() => applyVanWarehouseToItems(frm));
					}
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

		function applyVanWarehouseToItems(frm) {
			if (!isVanSalesInvoice(frm) || !frm.doc.custom_van_warehouse) return;

			(frm.doc.items || []).forEach((row) => {
				if (row.item_code && row.warehouse !== frm.doc.custom_van_warehouse) {
					frappe.model.set_value(row.doctype, row.name, "warehouse", frm.doc.custom_van_warehouse);
				}
			});
		}

		frappe.ui.form.on("Sales Invoice Item", {
			async custom_barcode_scan(frm, cdt, cdn) {
				const row = locals[cdt]?.[cdn];
				const barcode = row?.custom_barcode_scan?.trim();
				if (!barcode) return;

				const { message: item } = await frappe.call({
					method: "retail.domains.item.packing_scan.scan_barcode",
					args: { search_value: barcode },
				});
				if (!locals[cdt]?.[cdn] || row.custom_barcode_scan?.trim() !== barcode) return;
				if (!item?.item_code) {
					frappe.throw(__("Cannot find Item with this Barcode"));
				}

				// The server resolves custom_barcode_scan after ERPNext clears barcode
				// and conversion_factor in its item_code handler.
				row.barcode = item.barcode || barcode;
				row.uom = item.uom || null;
				if (row.item_code === item.item_code) {
					await frm.script_manager.trigger("item_code", cdt, cdn);
				} else {
					await frappe.model.set_value(cdt, cdn, "item_code", item.item_code);
				}
				frm.refresh_field("items");
			},
			item_code(frm, cdt, cdn) {
				const row = locals[cdt]?.[cdn];
				if (isVanSalesInvoice(frm) && row?.item_code && frm.doc.custom_van_warehouse) {
					frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.custom_van_warehouse);
				}
			},
			qty(frm, cdt, cdn) {
				updateFocQty(frm, cdt, cdn);
			},
		conversion_factor(frm, cdt, cdn) {
			updateFocQty(frm, cdt, cdn);
		},
		custom_foc_qty(frm, cdt, cdn) {
			updateFocQty(frm, cdt, cdn);
		},
	});

	function updateFocQty(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.custom_total_stock_qty === undefined) return;

		const totalQty = flt(row.qty) + flt(row.custom_foc_qty);
		if (flt(row.custom_total_stock_qty) === totalQty) return;

		const values = {
			custom_total_stock_qty: totalQty,
		};

		frappe.model.set_value(cdt, cdn, values);
		frm.refresh_field("items");
	}
	})();

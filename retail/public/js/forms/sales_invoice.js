(function () {
	if (!window.frappe?.ui?.form) return;

		frappe.ui.form.on("Sales Invoice", {
			before_validate(frm) {
				clearFetchedStockDefault(frm);
			},
			onload(frm) {
				if (frm.is_new() && !frm.doc.amended_from && !frm.doc.is_return &&
					!(frm.doc.items || []).some(row => row.item_code || row.delivery_note || row.sales_order)) {
					frm.__retail_fresh_stock_default = true;
					frm.set_value("update_stock", 1);
				}
			},
			onload_post_render(frm) {
				keepCompanyVisible(frm);
				applyVanSalesInvoiceState(frm);
				populateSalesPersonField(frm);
			},
			refresh(frm) {
				clearFetchedStockDefault(frm);
				installItemRefreshBatching(frm);
				const grid = frm.fields_dict.items?.grid;
				if (grid && !grid.__retail_id_order) {
					grid.__retail_id_order = true;
					const query = grid.set_custom_query;
					grid.set_custom_query = function (args) {
						query?.call(this, args);
						const endpoint = "retail.domains.item.desk_search.item_query_by_id";
						args.query = endpoint;
						// LinkSelector reads the field query immediately after this hook.
						// Override that one read, retaining normal ranked Link searches.
						const info = this.fieldinfo.item_code;
						const native = info?.get_query;
						if (typeof native === "function") {
							info.get_query = function (...values) {
								info.get_query = native;
								return {...native.apply(this, values), query: endpoint};
							};
						}
					};
				}
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

	function clearFetchedStockDefault(frm) {
		if (!frm.is_new() || !frm.__retail_fresh_stock_default) return;
		if ((frm.doc.items || []).some(row => row.delivery_note || row.sales_order || row.sales_invoice)) {
			frm.__retail_fresh_stock_default = false;
			frm.set_value("update_stock", 0);
		}
	}

	function installItemRefreshBatching(frm) {
		if (frm.__retail_item_refresh_batching) return;
		frm.__retail_item_refresh_batching = true;
		const refresh = frm.refresh_fields;
		let depth = 0, frame = null;
		const flush = () => {
			if (frame === null) return;
			cancelAnimationFrame(frame);
			frame = null;
			refresh.call(frm);
		};
		frm.refresh_fields = function (...args) {
			if (!depth || args.length || Number(frm.doc.docstatus || 0) !== 0) {
				if (frame !== null) { cancelAnimationFrame(frame); frame = null; }
				return refresh.apply(this, args);
			}
			// ERPNext still calculates every intermediate value. Paint once per
			// frame instead of rebuilding every control for each rate/discount event.
			if (frame === null) frame = requestAnimationFrame(flush);
		};
		const manager = frm.script_manager, trigger = manager.trigger;
		manager.trigger = function (event, cdt, cdn, ...args) {
			if (cdt !== "Sales Invoice Item" || Number(frm.doc.docstatus || 0) !== 0) {
				return trigger.call(this, event, cdt, cdn, ...args);
			}
			depth++;
			let result;
			try { result = trigger.call(this, event, cdt, cdn, ...args); }
			catch (error) { depth--; flush(); throw error; }
			return Promise.resolve(result).finally(() => { if (--depth === 0) flush(); });
		};
	}

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
				if (item.scale_barcode_type) {
					await frappe.model.set_value(cdt, cdn, "uom", item.uom);
					await retail.scale_sales.apply(frm, row, item);
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

(function () {
	if (!window.frappe?.ui?.form) return;

	const BARCODE_FIELD = "scan_barcode";
	const PROMO_FIELDS = ["promo_price", "promo_price_including_tax", "discount_percent", "discount_amount"];
	const DEFAULT_PRICE_LIST = "Standard Selling";

	frappe.ui.form.on("Promo Price", {
		promotion_scope(frm) {
			applyScope(frm, true);
		},
		refresh(frm) {
			applyScope(frm);
			preparePromoPriceFormatters(frm);
			refreshPromoMethodLocks(frm);
			addScanItemButton(frm);
			prepareBarcodeInput(frm);
		},
		onload_post_render(frm) {
			(frm.doc.products || []).forEach((row) => {
				const qty = flt(row.qty) || 1;
				row._promo_unit_current_price ??= flt(row.current_price) / qty;
				row._promo_unit_current_price_including_tax ??= flt(row.current_price_including_tax) / qty;
				if (flt(row.discount_percent) || flt(row.discount_amount)) {
					synchronizeDiscount(frm, row.doctype, row.name, row.discount_input || "Percent");
				}
				loadPurchasePrices(frm, row);
			});
			preparePromoPriceFormatters(frm);
			refreshPromoMethodLocks(frm);
			prepareBarcodeInput(frm);
		},
		scan_barcode(frm) {
			const barcode = (frm.doc?.[BARCODE_FIELD] || "").trim();
			if (!barcode) return;
			frm.set_value(BARCODE_FIELD, "");
			addScannedItem(frm, barcode);
		},
	});

	frappe.ui.form.on("Promo Price Item", {
		async item(frm, cdt, cdn) {
			const row = locals[cdt]?.[cdn];
			if (row?.item && !row._promo_populating) {
				await frappe.model.set_value(cdt, cdn, "item_group", "");
				await populateSelectedItem(frm, cdt, cdn);
			}
			lockPromoMethodFields(frm, cdt, cdn);
		},
		async item_group(frm, cdt, cdn) {
			const row = locals[cdt]?.[cdn];
			if (!row?.item_group) return;
			await frappe.model.set_value(cdt, cdn, "item", "");
			for (const field of ["barcode", "uom", "price_list"]) row[field] = "";
			for (const field of ["current_price", "current_price_including_tax", "purchase_price", "purchase_price_including_tax", "vat_rate", "discount_amount"]) row[field] = 0;
			row._promo_unit_current_price = row._promo_unit_current_price_including_tax = 0;
			if (row.discount_input === "Amount") {
				row.discount_percent = 0;
				row.discount_input = "";
			}
			frm.refresh_field("products");
			lockPromoMethodFields(frm, cdt, cdn);
		},
		uom(frm, cdt, cdn) {
			const row = locals[cdt]?.[cdn];
			if (row && !row._promo_populating) return loadPurchasePrices(frm, row);
		},
		qty(frm, cdt, cdn) {
			recalculateCurrentPrices(frm, cdt, cdn);
		},
		form_render(frm, cdt, cdn) {
			lockPromoMethodFields(frm, cdt, cdn);
		},
		promo_price(frm, cdt, cdn) {
			syncPromoPrices(frm, cdt, cdn, "exclusive");
			lockPromoMethodFields(frm, cdt, cdn);
		},
		promo_price_including_tax(frm, cdt, cdn) {
			syncPromoPrices(frm, cdt, cdn, "inclusive");
			lockPromoMethodFields(frm, cdt, cdn);
		},
		discount_percent(frm, cdt, cdn) {
			synchronizeDiscount(frm, cdt, cdn, "Percent");
		},
		discount_amount(frm, cdt, cdn) {
			synchronizeDiscount(frm, cdt, cdn, "Amount");
		},
	});

	function applyScope(frm, clear = false) {
		const scope = frm.doc.promotion_scope || ((frm.doc.products || []).some(row => row.item_group) ? "CATEGORY" : "ITEM");
		const target = { ITEM: "item", CATEGORY: "item_group", BRAND: "brand" }[scope];
		const grid = frm.fields_dict.products?.grid;
		if (grid) grid.retail_promotion_target = target;
		for (const field of ["item", "item_group", "brand"]) {
			grid?.update_docfield_property(field, "hidden", field !== target ? 1 : 0);
			grid?.update_docfield_property(field, "read_only", field !== target ? 1 : 0);
		}
		frm.toggle_display("scan_barcode_section", scope === "ITEM");
		frm.toggle_display("scan_barcode", scope === "ITEM");
		if (scope !== "ITEM") frm.remove_custom_button(__("Scan Barcode (Camera)"));
		if (clear) {
			for (const row of frm.doc.products || []) {
				for (const field of ["item", "item_group", "brand", "barcode", "uom", "price_list"]) row[field] = "";
				for (const field of ["current_price", "current_price_including_tax", "purchase_price", "purchase_price_including_tax", "vat_rate", "discount_amount"]) row[field] = 0;
				row._promo_unit_current_price = row._promo_unit_current_price_including_tax = 0;
				if (row.discount_input === "Amount") row.discount_percent = 0;
				row.discount_input = row.discount_percent ? "Percent" : "";
			}
			frm.dirty();
		}
		grid?.update_docfield_property("discount_amount", "read_only", scope !== "ITEM" ? 1 : 0);
		grid?.reset_grid();
		frm.refresh_field("products");
	}

	function synchronizeDiscount(frm, cdt, cdn, source) {
		const row = locals[cdt]?.[cdn];
		if (!row || row._promo_populating) return;
		const base = flt(row.current_price_including_tax);
		if (source === "Amount") {
			if (flt(row.discount_amount) && (row.item_group || base <= 0 || flt(row.discount_amount) < 0 || flt(row.discount_amount) > base)) {
				row.discount_amount = 0;
				row.discount_percent = 0;
				row.discount_input = "";
				frm.refresh_field("products");
				lockPromoMethodFields(frm, cdt, cdn);
				frappe.throw(__("Discount Amount requires an Item and must be between zero and its selling price including VAT."));
			}
			row.discount_percent = base ? flt(flt(row.discount_amount) / base * 100, 6) : 0;
			row.discount_input = flt(row.discount_amount) ? "Amount" : "";
		} else {
			if (flt(row.discount_percent) < 0 || flt(row.discount_percent) > 100) {
				row.discount_percent = row.discount_amount = 0;
				row.discount_input = "";
				frm.refresh_field("products");
				lockPromoMethodFields(frm, cdt, cdn);
				frappe.throw(__("Discount % must be between 0 and 100."));
			}
			row.discount_amount = row.item_group ? 0 : flt(base * flt(row.discount_percent) / 100, 2);
			row.discount_input = flt(row.discount_percent) ? "Percent" : "";
		}
		frm.refresh_field("products");
		lockPromoMethodFields(frm, cdt, cdn);
	}

	async function loadPurchasePrices(frm, row) {
		if (!row.item) return;
		const item = row.item;
		const uom = row.uom;
		const response = await frappe.call({
			method: "retail.promotions.promo_price.get_item_for_promo_price",
			args: { item_code: item, uom, price_list: row.price_list || frm.doc.price_list || DEFAULT_PRICE_LIST },
		});
		if (row.item !== item || row.uom !== uom || !(frm.doc.products || []).includes(row)) return;
		row.purchase_price = response.message.purchase_price;
		row.purchase_price_including_tax = response.message.purchase_price_including_tax;
		frm.refresh_field("products");
	}

	// Discount prices are previews, not fixed-rate inputs. Keep the saved price
	// fields untouched so validation and promotion consumers retain the discount rule.
	function preparePromoPriceFormatters(frm) {
		const grid = frm.fields_dict.products?.grid;
		if (!grid) return;
		for (const [fieldname, currentField] of [
			["promo_price", "current_price"],
			["promo_price_including_tax", "current_price_including_tax"],
		]) {
			const formatter = (value, df, options, doc) => {
				const price = flt(doc?.discount_percent)
					? flt(flt(doc[currentField]) * (1 - flt(doc.discount_percent) / 100), 2)
					: value;
				return frappe.form.formatters.Currency(price, df, options, doc);
			};
			const df = frappe.meta.get_docfield("Promo Price Item", fieldname, frm.doc.name);
			if (df) df.formatter = formatter;
			if (grid.fields_map?.[fieldname]) grid.fields_map[fieldname].formatter = formatter;
			for (const row of grid.grid_rows || []) {
				const rowDf = row.docfields?.find((field) => field.fieldname === fieldname);
				if (rowDf) rowDf.formatter = formatter;
			}
		}
		frm.refresh_field("products");
	}

	function refreshPromoMethodLocks(frm) {
		(frm.doc.products || []).forEach((row) => {
			lockPromoMethodFields(frm, row.doctype, row.name);
		});
	}

	function recalculateCurrentPrices(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row) return;

		const quantity = flt(row.qty);
		const unitCurrent = row._promo_unit_current_price ?? flt(row.current_price);
		const unitCurrentIncl =
			row._promo_unit_current_price_including_tax ?? flt(row.current_price_including_tax);
		row.current_price = unitCurrent * quantity;
		row.current_price_including_tax = unitCurrentIncl * quantity;
		if (row.discount_input || flt(row.discount_percent)) {
			synchronizeDiscount(frm, cdt, cdn, row.discount_input || "Percent");
		}
		frm.refresh_field("products");
	}

	function syncPromoPrices(frm, cdt, cdn, source) {
		const row = locals[cdt]?.[cdn];
		if (!row || row._syncing_promo_prices) return;

		const vatRate = flt(row.vat_rate) || getVatRateFromCurrentPrices(row);
		row._syncing_promo_prices = true;
		if (source === "exclusive") {
			row.promo_price_including_tax = flt(row.promo_price * (1 + vatRate / 100), 2);
		} else if (source === "inclusive") {
			row.promo_price = flt(row.promo_price_including_tax / (1 + vatRate / 100), 2);
		}
		row._syncing_promo_prices = false;
		frm.refresh_field("products");
	}

	function getVatRateFromCurrentPrices(row) {
		const exclusive = flt(row.current_price);
		const inclusive = flt(row.current_price_including_tax);
		return exclusive ? (inclusive / exclusive - 1) * 100 : 0;
	}

	async function populateSelectedItem(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row?.item || row._promo_populating) return;

		row._promo_populating = true;
		try {
			const response = await frappe.call({
				method: "retail.promotions.promo_price.get_item_for_promo_price",
				args: { item_code: row.item, price_list: frm.doc.price_list || DEFAULT_PRICE_LIST },
				freeze: true,
				freeze_message: __("Loading item prices..."),
			});
			const item = response.message;
			if (!item || locals[cdt]?.[cdn] !== row || row.item !== item.item) return;

			row._promo_unit_current_price = flt(item.current_price);
			row._promo_unit_current_price_including_tax = flt(item.current_price_including_tax);
			const updates = Object.entries(item).map(([fieldname, value]) => {
				if (["item", "qty"].includes(fieldname) || !frappe.meta.get_docfield(row.doctype, fieldname)) return null;
				return frappe.model.set_value(row.doctype, row.name, fieldname, value);
			});
			if (!flt(row.qty)) await frappe.model.set_value(row.doctype, row.name, "qty", 1);
			await Promise.all(updates);
			row._promo_populating = false;
			recalculateCurrentPrices(frm, cdt, cdn);
			lockPromoMethodFields(frm, cdt, cdn);
		} catch (error) {
			frappe.show_alert({ message: __("Could not load item prices"), indicator: "red" });
		} finally {
			row._promo_populating = false;
		}
	}

	function addScanItemButton(frm) {
		if (frm.doc.promotion_scope && frm.doc.promotion_scope !== "ITEM") return;
		frm.remove_custom_button(__("Scan Barcode"));
		frm.remove_custom_button(__("Scan Item"));
		frm.add_custom_button(__("Scan Barcode (Camera)"), () => scanItem(frm), null, "scan-item");
	}

	function prepareBarcodeInput(frm) {
		const scanField = frm.fields_dict?.[BARCODE_FIELD];
		if (!scanField?.$input || scanField._promo_price_barcode_ready) {
			return;
		}

		scanField._promo_price_barcode_ready = true;
		scanField.$input.on("keydown.barcode", (event) => {
			if (event.key !== "Enter") {
				return;
			}
			event.preventDefault();
			const barcode = (scanField.get_input_value?.() || scanField.$input.val() || "").trim();
			if (!barcode) return;

			frm.set_value(BARCODE_FIELD, "");
			addScannedItem(frm, barcode);
		});
	}

	function scanItem(frm) {
		if (frappe.ui.Scanner) {
			new frappe.ui.Scanner({
				dialog: true,
				multiple: false,
				on_scan(data) {
					addScannedItem(frm, data?.decodedText || data?.text || data);
				},
			});
			return;
		}

		frappe.prompt(
			[
				{
					fieldname: "barcode",
					fieldtype: "Data",
					options: "Barcode",
					label: __("Barcode or QR Code"),
					reqd: 1,
				},
			],
			(values) => addScannedItem(frm, values.barcode),
			__("Add Item"),
			__("Add"),
		);
	}
function addScannedItem(frm, barcode) {
	barcode = (barcode || "").trim();
	if (!barcode || (frm.doc.promotion_scope && frm.doc.promotion_scope !== "ITEM")) return;

	frappe
		.call({
			method: "retail.promotions.promo_price.get_item_for_promo_price",
			args: { barcode, price_list: frm.doc.price_list || DEFAULT_PRICE_LIST },
			freeze: true,
			freeze_message: __("Loading item prices..."),
		})
			.then(async (response) => {
			const item = response.message;
			if (!item) return;

			const existingRow = (frm.doc.products || []).find((row) => {
				if (!row) return false;
				return (
					row.item === item.item &&
					row.uom === item.uom &&
					row.price_list === item.price_list &&
					row.barcode === item.barcode
				);
			});
			const emptyRow = (frm.doc.products || []).find((row) => row && !row.item && !row.item_group);

				if (existingRow) {
					const nextQty = flt(existingRow.qty || 0) + flt(item.qty || 1);
					existingRow._promo_unit_current_price = flt(item.current_price);
					existingRow._promo_unit_current_price_including_tax = flt(item.current_price_including_tax);
					const nextPromo = flt(existingRow.promo_price || 0) + flt(item.promo_price || 0);
					const nextPromoIncl =
						flt(existingRow.promo_price_including_tax || 0) + flt(item.promo_price_including_tax || 0);

					existingRow.purchase_price = item.purchase_price;
					existingRow.purchase_price_including_tax = item.purchase_price_including_tax;
					existingRow.qty = nextQty;
					recalculateCurrentPrices(frm, existingRow.doctype, existingRow.name);
					existingRow.promo_price = nextPromo;
					existingRow.promo_price_including_tax = nextPromoIncl;
				} else {
					const row = emptyRow || frappe.model.add_child(frm.doc, "Promo Price Item", "products");
					row._promo_populating = true;
					row._promo_unit_current_price = flt(item.current_price);
					row._promo_unit_current_price_including_tax = flt(item.current_price_including_tax);
					const updates = Object.entries(item).map(([fieldname, value]) => {
						if (frappe.meta.get_docfield(row.doctype, fieldname)) {
							return frappe.model.set_value(row.doctype, row.name, fieldname, value);
						}
						return null;
					});
					await Promise.all(updates);
					row._promo_populating = false;
				}

				frm.refresh_field("products");
				frappe.show_alert({ message: __("Item {0} added", [item.item]), indicator: "green" });
			})
		.catch(() => {
			frappe.show_alert({ message: __("Could not load barcode {0}", [barcode]), indicator: "red" });
		});
}

	function lockPromoMethodFields(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row) return;

		const selectedField = (flt(row.discount_percent) || flt(row.discount_amount))
			? (row.discount_input === "Amount" ? "discount_amount" : "discount_percent")
			: (flt(row.promo_price) || flt(row.promo_price_including_tax))
				? "promo_price"
				: null;
		const gridRow = frm.fields_dict.products?.grid?.grid_rows_by_docname?.[cdn];
		if (!gridRow) {
			frm.refresh_field("products");
			return;
		}

		PROMO_FIELDS.forEach((fieldname) => {
			const isPromoPriceField = fieldname === "promo_price" || fieldname === "promo_price_including_tax";
			const readOnly = (fieldname === "discount_amount" && !row.item) ||
				(selectedField && selectedField !== fieldname && !(selectedField === "promo_price" && isPromoPriceField)) ? 1 : 0;
			const df = gridRow.docfields?.find((field) => field.fieldname === fieldname);
			if (df) df.read_only = readOnly;
			// Inline controls do not exist until the row is opened for editing.
			const field = gridRow.on_grid_fields_dict?.[fieldname] || gridRow.grid_form?.fields_dict?.[fieldname];
			if (field) {
				field.df.read_only = readOnly;
				field.refresh();
			}
		});
	}

})();

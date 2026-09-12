(function () {
	if (!window.frappe?.ui?.form) return;

	const BARCODE_FIELD = "scan_barcode";
	const PROMO_FIELDS = ["promo_price", "promo_price_including_tax", "discount_percent"];
	const DEFAULT_PRICE_LIST = "Standard Selling";

	frappe.ui.form.on("Promo Price", {
		refresh(frm) {
			refreshPromoMethodLocks(frm);
			addScanItemButton(frm);
			prepareBarcodeInput(frm);
		},
		onload_post_render(frm) {
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
		item(frm, cdt, cdn) {
			populateSelectedItem(frm, cdt, cdn);
			setDefaultUom(frm, cdt, cdn);
			lockPromoMethodFields(frm, cdt, cdn);
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
			lockPromoMethodFields(frm, cdt, cdn);
		},
	});

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
		frm.refresh_field("products");
	}

	function syncPromoPrices(frm, cdt, cdn, source) {
		const row = locals[cdt]?.[cdn];
		if (!row || row._syncing_promo_prices) return;

		const vatRate = flt(row.vat_rate) || getVatRateFromCurrentPrices(row);
		if (!vatRate) return;

		row._syncing_promo_prices = true;
		if (source === "exclusive" && flt(row.promo_price)) {
			row.promo_price_including_tax = flt(row.promo_price * (1 + vatRate / 100), 2);
		} else if (source === "inclusive" && flt(row.promo_price_including_tax)) {
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
			if (!item || locals[cdt]?.[cdn] !== row) return;

			row._promo_unit_current_price = flt(item.current_price);
			row._promo_unit_current_price_including_tax = flt(item.current_price_including_tax);
			const updates = Object.entries(item).map(([fieldname, value]) => {
				if (fieldname === "item" || !frappe.meta.get_docfield(row.doctype, fieldname)) return null;
				return frappe.model.set_value(row.doctype, row.name, fieldname, value);
			});
			if (!flt(row.qty)) await frappe.model.set_value(row.doctype, row.name, "qty", 1);
			await Promise.all(updates);
			recalculateCurrentPrices(frm, cdt, cdn);
			lockPromoMethodFields(frm, cdt, cdn);
		} catch (error) {
			frappe.show_alert({ message: __("Could not load item prices"), indicator: "red" });
		} finally {
			row._promo_populating = false;
		}
	}

	function addScanItemButton(frm) {
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
	if (!barcode) return;

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
			const emptyRow = (frm.doc.products || []).find((row) => row && !row.item);

				if (existingRow) {
					const nextQty = flt(existingRow.qty || 0) + flt(item.qty || 1);
					existingRow._promo_unit_current_price = flt(item.current_price);
					existingRow._promo_unit_current_price_including_tax = flt(item.current_price_including_tax);
					const nextPromo = flt(existingRow.promo_price || 0) + flt(item.promo_price || 0);
					const nextPromoIncl =
						flt(existingRow.promo_price_including_tax || 0) + flt(item.promo_price_including_tax || 0);

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

		const selectedField = flt(row.discount_percent)
			? "discount_percent"
			: (flt(row.promo_price) || flt(row.promo_price_including_tax))
				? "promo_price"
				: null;
		const gridRow = frm.fields_dict.products?.grid?.grid_rows_by_docname?.[cdn];
		if (!gridRow) {
			frm.refresh_field("products");
			return;
		}

		PROMO_FIELDS.forEach((fieldname) => {
			const field = gridRow.get_field(fieldname);
			if (!field) return;

			const isPromoPriceField = fieldname === "promo_price" || fieldname === "promo_price_including_tax";
			field.df.read_only = selectedField && selectedField !== fieldname && !(selectedField === "promo_price" && isPromoPriceField) ? 1 : 0;
			field.refresh();
		});
	}

	function setDefaultUom(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row?.item || row.uom) return;

		frappe.db.get_value("Item", row.item, "stock_uom").then((response) => {
			const stockUom = response?.message?.stock_uom;
			if (!stockUom) return;

			frappe.model.set_value(cdt, cdn, "uom", stockUom);
			frm.refresh_field("products");
		});
	}
})();

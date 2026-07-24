/* All Item Master form behaviour lives here: pricing, VAT and barcode cleanup. */
(function () {
	if (!window.frappe?.ui?.form) return;

	const vatPriceFields = {
		sales: {
			template: "custom_tax", entry: "custom_sales_rate_entry",
			inclusive: "custom_sales_rate_includes_vat", net: "custom_sales_net_rate",
			vat: "custom_sales_vat_amount", gross: "custom_sales_gross_rate", base: "standard_rate",
		},
		purchase: {
			template: "custom_purchase_tax_template", entry: "custom_purchase_rate_entry",
			inclusive: "custom_purchase_rate_includes_vat", net: "custom_purchase_net_rate",
			vat: "custom_purchase_vat_amount", gross: "custom_purchase_gross_rate",
			base: "custom_default_purchase_rate",
		},
	};

	const packingVatFields = {
		purchase: {
			entry: "purchase_rate", mode: "purchase_vat_mode", rate: "purchase_vat_rate",
			confirmed: "purchase_vat_confirmed", net: "purchase_net_rate",
			vat: "purchase_vat_amount", gross: "purchase_gross_rate",
			status: "purchase_vat_status", template: "custom_purchase_tax_template",
			label: __("Purchase"),
		},
		selling: {
			entry: "selling_rate", mode: "selling_vat_mode", rate: "selling_vat_rate",
			confirmed: "selling_vat_confirmed", net: "selling_net_rate",
			vat: "selling_vat_amount", gross: "selling_gross_rate",
			status: "selling_vat_status", template: "custom_tax",
			label: __("Selling"),
		},
	};
	const arabicItemNameField = "custom_arabic_item_name";
	const arabicTranslationDelay = 900;

	frappe.ui.form.on("Item", {
		refresh(frm) {
			setDefaultVatIncludes(frm);
			setupArabicItemNameField(frm);
			addArabicTranslationButton(frm);
			queueLastPurchaseRateLookup(frm);
			setOpeningAveragePurchaseRate(frm, false);
			refreshVatPrices(frm);
			refreshPackingVatRows(frm);
			refreshMargin(frm);
			addPackingVatButton(frm);
			addZebraLabelButton(frm);
		},
		item_name(frm) {
			queueArabicItemNameTranslation(frm);
			queueLastPurchaseRateLookup(frm);
		},
		item_code(frm) {
			queueArabicItemNameTranslation(frm);
		},
		custom_arabic_item_name(frm) {
			const currentArabic = (frm.doc[arabicItemNameField] || "").trim();
			const lastAutoValue = (frm._arabic_item_name_auto_value || "").trim();
			if (frm._setting_arabic_item_name || currentArabic === lastAutoValue) return;
			frm._arabic_item_name_touched = true;
		},
		last_purchase_rate(frm) {
			if (frm._setting_fetched_item_prices) return;
			setOpeningAveragePurchaseRate(frm, true);
		},
		custom_default_purchase_rate(frm) {
			if (frm._setting_fetched_item_prices) return;
			setOpeningAveragePurchaseRate(frm, true);
		},
		custom_tax(frm) {
			refreshVatPrices(frm, "sales");
			refreshPackingFromItemRates(frm, "selling");
		},
		custom_purchase_tax_template(frm) {
			refreshVatPrices(frm, "purchase");
			refreshPackingFromItemRates(frm, "purchase");
		},
		custom_sales_rate_entry(frm) { refreshVatPrices(frm, "sales").then(() => refreshPackingFromItemRates(frm, "selling")); },
		custom_sales_rate_includes_vat(frm) { refreshVatPrices(frm, "sales").then(() => refreshPackingFromItemRates(frm, "selling")); },
		custom_purchase_rate_entry(frm) { refreshVatPrices(frm, "purchase").then(() => refreshPackingFromItemRates(frm, "purchase")); },
		custom_purchase_rate_includes_vat(frm) { refreshVatPrices(frm, "purchase").then(() => refreshPackingFromItemRates(frm, "purchase")); },
		custom_average_purchase_rate(frm) { refreshMargin(frm); },
		custom_b2b(frm) { refreshMargin(frm); },
		validate(frm) { removeEmptyBarcodeRows(frm); },
		before_save(frm) { removeEmptyBarcodeRows(frm); },
	});

	function addZebraLabelButton(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Print Zebra Label"), () => showZebraLabelDialog(frm), __("Retail"));
	}

	async function showZebraLabelDialog(frm) {
		const defaultFormat = await getDefaultZebraLabelFormat();
		const dialog = new frappe.ui.Dialog({
			title: __("Print Zebra Label"),
			fields: [
				{
					fieldname: "label_format",
					label: __("Label Format"),
					fieldtype: "Link",
					options: "Zebra Label Format",
					reqd: 1,
					default: defaultFormat,
					get_query: () => ({ filters: { enabled: 1, reference_doctype: "Item" } }),
				},
				{
					fieldname: "copies",
					label: __("Copies"),
					fieldtype: "Int",
					default: 1,
					reqd: 1,
				},
				{
					fieldname: "price",
					label: __("Price"),
					fieldtype: "Currency",
					default: frm.doc.standard_rate || frm.doc.custom_sales_gross_rate || frm.doc.custom_sales_rate_entry || 0,
				},
				{
					fieldname: "currency",
					label: __("Currency"),
					fieldtype: "Data",
					default: "AED",
				},
				{
					fieldname: "preview",
					fieldtype: "HTML",
				},
				{
					fieldname: "rendered_zpl",
					label: __("Rendered ZPL"),
					fieldtype: "Code",
					options: "ZPL",
					read_only: 1,
				},
			],
			primary_action_label: __("Print"),
			primary_action: async (values) => {
				await frappe.call({
					method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.print_label",
					args: {
						label_format: values.label_format,
						item: frm.doc.name,
						copies: values.copies,
						price: values.price,
						currency: values.currency,
					},
					freeze: true,
					freeze_message: __("Sending to Zebra printer"),
				});
				dialog.hide();
				frappe.show_alert({ message: __("Sent to Zebra printer"), indicator: "green" });
			},
			secondary_action_label: __("Preview"),
			secondary_action: () => previewZebraLabelDialog(frm, dialog),
		});

		dialog.show();
		await previewZebraLabelDialog(frm, dialog);
	}

	async function getDefaultZebraLabelFormat() {
		const { message } = await frappe.call({
			method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.get_default_format",
			args: { label_type: "Barcode Label" },
		});
		return message;
	}

	async function previewZebraLabelDialog(frm, dialog) {
		const values = dialog.get_values();
		if (!values?.label_format) return;
		const { message } = await frappe.call({
			method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.render_label",
			args: {
				label_format: values.label_format,
				item: frm.doc.name,
				copies: values.copies,
				price: values.price,
				currency: values.currency,
			},
		});
		dialog.fields_dict.preview.$wrapper.html(message.preview_html);
		dialog.set_value("rendered_zpl", message.zpl);
	}

	frappe.ui.form.on("Retail Packing Detail", {
		purchase_rate(frm, cdt, cdn) {
			if (isPackingRowProgrammaticUpdate(cdt, cdn)) return;
			resetPackingVatConfirmation(cdt, cdn, "purchase");
			refreshPackingVatRow(frm, cdt, cdn, "purchase", "entry").then(() => updateItemRateFromPacking(frm, cdt, cdn, "purchase", "entry"));
		},
		selling_rate(frm, cdt, cdn) {
			if (isPackingRowProgrammaticUpdate(cdt, cdn)) return;
			resetPackingVatConfirmation(cdt, cdn, "selling");
			refreshPackingVatRow(frm, cdt, cdn, "selling", "entry");
		},
		purchase_net_rate(frm, cdt, cdn) {
			if (isPackingRowProgrammaticUpdate(cdt, cdn)) return;
			resetPackingVatConfirmation(cdt, cdn, "purchase");
			refreshPackingVatRow(frm, cdt, cdn, "purchase", "net").then(() => updateItemRateFromPacking(frm, cdt, cdn, "purchase", "net"));
		},
		purchase_gross_rate(frm, cdt, cdn) {
			if (isPackingRowProgrammaticUpdate(cdt, cdn)) return;
			resetPackingVatConfirmation(cdt, cdn, "purchase");
			refreshPackingVatRow(frm, cdt, cdn, "purchase", "gross").then(() => updateItemRateFromPacking(frm, cdt, cdn, "purchase", "gross"));
		},
		selling_net_rate(frm, cdt, cdn) {
			if (isPackingRowProgrammaticUpdate(cdt, cdn)) return;
			resetPackingVatConfirmation(cdt, cdn, "selling");
			refreshPackingVatRow(frm, cdt, cdn, "selling", "net");
		},
		selling_gross_rate(frm, cdt, cdn) {
			if (isPackingRowProgrammaticUpdate(cdt, cdn)) return;
			resetPackingVatConfirmation(cdt, cdn, "selling");
			refreshPackingVatRow(frm, cdt, cdn, "selling", "gross");
		},
		purchase_vat_mode(frm, cdt, cdn) {
			resetPackingVatConfirmation(cdt, cdn, "purchase");
			refreshPackingVatRow(frm, cdt, cdn, "purchase");
		},
		selling_vat_mode(frm, cdt, cdn) {
			resetPackingVatConfirmation(cdt, cdn, "selling");
			refreshPackingVatRow(frm, cdt, cdn, "selling");
		},
		purchase_vat_rate(frm, cdt, cdn) {
			resetPackingVatConfirmation(cdt, cdn, "purchase");
			refreshPackingVatRow(frm, cdt, cdn, "purchase");
		},
		selling_vat_rate(frm, cdt, cdn) {
			resetPackingVatConfirmation(cdt, cdn, "selling");
			refreshPackingVatRow(frm, cdt, cdn, "selling");
		},
		purchase_vat_confirmed(frm, cdt, cdn) {
			refreshPackingVatRow(frm, cdt, cdn, "purchase");
		},
		selling_vat_confirmed(frm, cdt, cdn) {
			refreshPackingVatRow(frm, cdt, cdn, "selling");
		},
		custom_retail_packing_detail_add(frm, cdt, cdn) {
			setPackingRowFromItemRates(frm, cdt, cdn).then(() => refreshPackingVatRow(frm, cdt, cdn));
		},
		conversion_factor(frm, cdt, cdn) {
			setPackingRowFromItemRates(frm, cdt, cdn).then(() => refreshPackingVatRow(frm, cdt, cdn));
		},
	});

	function setDefaultVatIncludes(frm) {
		if (!frm.is_new() || frm._retail_vat_defaults_applied) return;
		frm._retail_vat_defaults_applied = true;
		const updates = {};
		if (!cint(frm.doc.custom_purchase_rate_includes_vat)) updates.custom_purchase_rate_includes_vat = 1;
		if (!cint(frm.doc.custom_sales_rate_includes_vat)) updates.custom_sales_rate_includes_vat = 1;
		if (Object.keys(updates).length) frm.set_value(updates);
	}

	function setOpeningAveragePurchaseRate(frm, overwrite) {
		if (!frm.is_new() || (!overwrite && frm.doc.custom_average_purchase_rate)) return;
		frm.set_value("custom_average_purchase_rate", frm.doc.custom_default_purchase_rate || frm.doc.last_purchase_rate || 0);
	}

	function queueLastPurchaseRateLookup(frm) {
		if (!frm.is_new()) return;

		clearTimeout(frm._last_purchase_rate_lookup);
		const itemName = (frm.doc.item_name || "").trim();
		if (!itemName) {
			clearFetchedItemPrices(frm);
			return;
		}

		frm._last_purchase_rate_lookup = setTimeout(() => {
			setLastPurchaseRateFromSameItemName(frm, itemName);
		}, 350);
	}

	function setLastPurchaseRateFromSameItemName(frm, requestedItemName) {
		if (!frm.is_new() || !requestedItemName) return;

		frappe.call({
			method: "retail.domains.item.item_price_sync.get_latest_item_name_prices",
			args: {
				item_name: requestedItemName,
				uom: frm.doc.stock_uom || "Nos",
			},
			callback({ message }) {
				if (!frm.is_new() || (frm.doc.item_name || "").trim() !== requestedItemName) return;
				const prices = message || {};
				const buyingRate = flt(prices.buying_rate);
				const averageRate = flt(prices.average_purchase_rate);
				const sellingRate = flt(prices.selling_rate);
				if (!buyingRate && !sellingRate) {
					clearFetchedItemPrices(frm);
					return;
				}

				frm._last_purchase_rate_source = prices.source_item || prices.selling_source_item || null;
				const updates = {};
				if (buyingRate) {
					updates.last_purchase_rate = buyingRate;
					updates.custom_default_purchase_rate = buyingRate;
					updates.custom_average_purchase_rate = averageRate || buyingRate;
				}
				if (sellingRate) {
					updates.custom_sales_rate_entry = sellingRate;
					updates.custom_sales_net_rate = sellingRate;
					updates.custom_sales_gross_rate = sellingRate;
					updates.standard_rate = sellingRate;
				}
				frm._setting_fetched_item_prices = true;
				Promise.resolve(frappe.model.set_value("Item", frm.doc.name, updates)).then(() => {
					frm._setting_fetched_item_prices = false;
					refreshMargin(frm);
				});
			},
		});
	}

	function clearFetchedItemPrices(frm) {
		frm._last_purchase_rate_source = null;
		frm.set_value("last_purchase_rate", 0);
		frm.set_value("custom_default_purchase_rate", 0);
		frm.set_value("custom_average_purchase_rate", 0);
	}

	function refreshVatPrices(frm, direction) {
		const work = (direction ? [direction] : ["sales", "purchase"]).map((side) => calculateVatPrice(frm, side));
		return Promise.all(work);
	}

	function calculateVatPrice(frm, direction) {
		const fields = vatPriceFields[direction];
		const entry = frm.doc[fields.entry];
		if (entry === undefined || entry === null || entry === "") return;
		if (flt(entry) <= 0) return;

		return frappe.call({
			method: "retail.domains.item.vat_pricing.get_item_tax_rate",
			args: { template: frm.doc[fields.template] },
			callback: ({ message }) => {
				const rate = flt(message || 0);
				const entered = flt(entry);
				const inclusive = cint(frm.doc[fields.inclusive]);
				const net = inclusive && rate ? entered / (1 + rate / 100) : entered;
				const vat = inclusive ? entered - net : net * rate / 100;
				const gross = inclusive ? entered : net + vat;
				const updates = {
					[fields.base]: flt(net, 2), [fields.net]: flt(net, 2),
					[fields.vat]: flt(vat, 2), [fields.gross]: flt(gross, 2),
				};
				if (direction === "purchase") updates.last_purchase_rate = flt(net, 2);
				Promise.resolve(setValuesIfChanged(frm.doc, "Item", frm.doc.name, updates))
					.then(() => refreshMargin(frm));
			},
		});
	}

	function addPackingVatButton(frm) {
		if (!frm.fields_dict.custom_retail_packing_detail) return;
		frm.add_custom_button(__("Confirm Packing VAT"), () => {
			refreshPackingVatRows(frm).then(() => showPackingVatDialog(frm));
		}, __("Retail"));
	}

	function refreshPackingVatRows(frm, direction, skipGridRefresh) {
		if (!Array.isArray(frm.doc.custom_retail_packing_detail)) return Promise.resolve();

		const work = [];
		(frm.doc.custom_retail_packing_detail || []).forEach((row) => {
			work.push(refreshPackingVatRow(frm, row.doctype, row.name, direction));
		});
		return Promise.all(work).then(() => {
			if (!skipGridRefresh) frm.refresh_field("custom_retail_packing_detail");
			return null;
		});
	}

	function refreshPackingVatRow(frm, cdt, cdn, direction, sourceField) {
		const row = locals[cdt]?.[cdn];
		if (!row) return Promise.resolve();

		const sides = direction ? [direction] : ["purchase", "selling"];
		return Promise.all(sides.map((side) => calculatePackingVatSide(frm, cdt, cdn, side, sourceField)))
			.then(() => setPackingMargin(cdt, cdn));
	}

	function calculatePackingVatSide(frm, cdt, cdn, direction, sourceField) {
		const row = locals[cdt]?.[cdn];
		const fields = packingVatFields[direction];
		if (!row || !fields) return Promise.resolve();
		if (!sourceField && row[fields.entry] === undefined) return Promise.resolve();

		return getTemplateVatRate(frm, frm.doc[fields.template]).then((defaultRate) => {
			let entered = flt(row[fields.entry]);
			const rate = hasEnteredValue(row[fields.rate]) ? flt(row[fields.rate]) : flt(defaultRate);
			let mode = row[fields.mode] || getDefaultPackingVatMode(frm, direction);
			let net;
			let gross;
			let vat;
			const divisor = 1 + rate / 100;

			if (sourceField === "net") {
				net = flt(row[fields.net]);
				vat = net * rate / 100;
				gross = net + vat;
				mode = "Excluding VAT";
				entered = net;
			} else if (sourceField === "gross") {
				gross = flt(row[fields.gross]);
				net = rate && divisor ? gross / divisor : gross;
				vat = gross - net;
				mode = "Including VAT";
				entered = gross;
			} else {
				const inclusive = mode === "Including VAT";
				net = inclusive && rate ? entered / divisor : entered;
				vat = inclusive ? entered - net : net * rate / 100;
				gross = inclusive ? entered : net + vat;
			}
			const status = getPackingVatStatus(mode, rate, row[fields.confirmed]);

			return setPackingValuesWithoutReentry(row, cdt, cdn, {
				[fields.entry]: flt(entered, 2),
				[fields.mode]: mode,
				[fields.rate]: flt(rate, 3),
				[fields.net]: flt(net, 2),
				[fields.vat]: flt(vat, 2),
				[fields.gross]: flt(gross, 2),
				[fields.status]: status,
			});
		});
	}

	function refreshPackingFromItemRates(frm, direction) {
		if (!Array.isArray(frm.doc.custom_retail_packing_detail)) return Promise.resolve();
		if (direction === "selling") return refreshPackingVatRows(frm, direction);
		const work = [];
		(frm.doc.custom_retail_packing_detail || []).forEach((row) => {
			work.push(setPackingRowFromItemRates(frm, row.doctype, row.name, direction));
		});
		return Promise.all(work).then(() => refreshPackingVatRows(frm, direction));
	}

	function setPackingRowFromItemRates(frm, cdt, cdn, direction) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.__retail_syncing_from_item) return Promise.resolve();

		const sides = direction ? [direction] : ["purchase"];
		if (!sides.includes("purchase")) return Promise.resolve();
		const updates = {};
		sides.forEach((side) => {
			const fields = packingVatFields[side];
			const state = getItemRateState(frm, side);
			const factor = flt(row.conversion_factor || 1) || 1;
			const mode = getDefaultPackingVatMode(frm, side);
			const net = state.net * factor;
			const gross = state.gross * factor;
			updates[fields.mode] = mode;
			updates[fields.entry] = flt(mode === "Including VAT" ? gross : net, 2);
			updates[fields.net] = flt(net, 2);
			updates[fields.vat] = flt(gross - net, 2);
			updates[fields.gross] = flt(gross, 2);
		});

		row.__retail_syncing_from_item = true;
		return setPackingValuesWithoutReentry(row, cdt, cdn, updates).finally(() => {
			row.__retail_syncing_from_item = false;
		});
	}

	function updateItemRateFromPacking(frm, cdt, cdn, direction, sourceField) {
		const row = locals[cdt]?.[cdn];
		const fields = packingVatFields[direction];
		if (!row || row.__retail_syncing_from_item || row.__retail_updating_item_rate) return Promise.resolve();
		if (direction === "selling") return Promise.resolve();

		const factor = flt(row.conversion_factor || 1) || 1;
		const rowNet = sourceField === "gross" || sourceField === "entry" ? flt(row[fields.net]) : flt(row[fields.net]);
		const rowGross = sourceField === "net" || sourceField === "entry" ? flt(row[fields.gross]) : flt(row[fields.gross]);
		if (rowNet <= 0 || factor <= 0) return Promise.resolve();

		const net = flt(rowNet / factor, 2);
		const gross = flt(rowGross / factor, 2);
		const updates = direction === "purchase"
			? {
				custom_purchase_rate_entry: gross,
				custom_purchase_rate_includes_vat: 1,
				custom_purchase_net_rate: net,
				custom_purchase_vat_amount: flt(gross - net, 2),
				custom_purchase_gross_rate: gross,
				custom_default_purchase_rate: net,
				last_purchase_rate: net,
			}
			: {
				custom_sales_rate_entry: gross,
				custom_sales_rate_includes_vat: 1,
				custom_sales_net_rate: net,
				custom_sales_vat_amount: flt(gross - net, 2),
				custom_sales_gross_rate: gross,
				standard_rate: net,
			};

		row.__retail_updating_item_rate = true;
		return frm.set_value(updates).then(() => {
			refreshMargin(frm);
			return refreshPackingVatRows(frm, direction, true);
		}).finally(() => {
			row.__retail_updating_item_rate = false;
		});
	}

	function isPackingRowProgrammaticUpdate(cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		return !!(row?.__retail_calculating_vat || row?.__retail_syncing_from_item || row?.__retail_updating_item_rate);
	}

	function setPackingValuesWithoutReentry(row, cdt, cdn, values) {
		row.__retail_calculating_vat = true;
		return frappe.model.set_value(cdt, cdn, values).finally(() => {
			row.__retail_calculating_vat = false;
		});
	}

	function getItemRateState(frm, direction) {
		const prefix = direction === "purchase" ? "custom_purchase" : "custom_sales";
		const fallbackNet = direction === "purchase"
			? flt(frm.doc.custom_default_purchase_rate || frm.doc.last_purchase_rate)
			: flt(frm.doc.standard_rate);
		const net = flt(frm.doc[`${prefix}_net_rate`] || fallbackNet);
		const gross = flt(frm.doc[`${prefix}_gross_rate`] || net);
		return { net, gross };
	}

	function getDefaultPackingVatMode(frm, direction) {
		const inclusiveField = direction === "purchase"
			? "custom_purchase_rate_includes_vat"
			: "custom_sales_rate_includes_vat";
		return cint(frm.doc[inclusiveField]) ? "Including VAT" : "Excluding VAT";
	}

	function setPackingMargin(cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.packing_margin === undefined) return Promise.resolve();

		return frappe.model.set_value(
			cdt,
			cdn,
			"packing_margin",
			flt(flt(row.selling_net_rate) - flt(row.purchase_net_rate), 2)
		);
	}

	function resetPackingVatConfirmation(cdt, cdn, direction) {
		const row = locals[cdt]?.[cdn];
		const fields = packingVatFields[direction];
		if (!row || !fields || !row[fields.confirmed]) return;
		frappe.model.set_value(cdt, cdn, fields.confirmed, 0);
	}

	function getTemplateVatRate(frm, template) {
		if (!template) return Promise.resolve(0);

		frm._packing_vat_rate_cache = frm._packing_vat_rate_cache || {};
		if (frm._packing_vat_rate_cache[template] !== undefined) {
			return Promise.resolve(frm._packing_vat_rate_cache[template]);
		}

		return frappe.call({
			method: "retail.domains.item.vat_pricing.get_item_tax_rate",
			args: { template },
		}).then(({ message }) => {
			frm._packing_vat_rate_cache[template] = flt(message || 0);
			return frm._packing_vat_rate_cache[template];
		});
	}

	function getPackingVatStatus(mode, rate, confirmed) {
		if (!rate) return __("Exempt");
		const prefix = mode === "Including VAT" ? __("Incl") : __("Excl");
		const text = `${prefix} ${flt(rate, 3)}%`;
		return confirmed ? __("{0} OK", [text]) : __("{0} Pending", [text]);
	}

	function showPackingVatDialog(frm) {
		const rows = frm.doc.custom_retail_packing_detail || [];
		if (!rows.length) {
			frappe.msgprint(__("Add packing rows before confirming VAT."));
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Confirm Packing VAT"),
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "preview" }],
			primary_action_label: __("Confirm All VAT"),
			primary_action() {
				const updates = [];
				rows.forEach((row) => {
					updates.push(frappe.model.set_value(row.doctype, row.name, {
						purchase_vat_confirmed: 1,
						selling_vat_confirmed: 1,
					}));
				});

				Promise.all(updates)
					.then(() => refreshPackingVatRows(frm))
					.then(() => {
						dialog.hide();
						frappe.show_alert({ message: __("Packing VAT confirmed"), indicator: "green" });
					});
			},
		});

		dialog.fields_dict.preview.$wrapper.html(getPackingVatDialogHtml(rows));
		dialog.show();
	}

	function getPackingVatDialogHtml(rows) {
		const cards = rows.map((row, index) => `
			<div class="packing-vat-card">
				<div class="packing-vat-card__head">
					<strong>${index + 1}. ${escapeHtml(row.barcode || row.uom || __("Packing Row"))}</strong>
					<span>${escapeHtml(row.uom || "")}</span>
				</div>
				<div class="packing-vat-sides">
					${getPackingVatSideHtml(row, "purchase")}
					${getPackingVatSideHtml(row, "selling")}
				</div>
			</div>
		`).join("");

		return `
			<style>
				.packing-vat-help { color: var(--text-muted); margin-bottom: 12px; }
				.packing-vat-card { border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 12px; overflow: hidden; }
				.packing-vat-card__head { align-items: center; background: var(--subtle-fg); display: flex; justify-content: space-between; padding: 10px 12px; }
				.packing-vat-sides { display: grid; gap: 0; grid-template-columns: repeat(2, minmax(0, 1fr)); }
				.packing-vat-side { padding: 12px; }
				.packing-vat-side + .packing-vat-side { border-left: 1px solid var(--border-color); }
				.packing-vat-side__title { align-items: center; display: flex; justify-content: space-between; margin-bottom: 8px; }
				.packing-vat-pill { border-radius: 999px; font-size: 12px; padding: 3px 8px; }
				.packing-vat-pill.ok { background: var(--green-100); color: var(--green-700); }
				.packing-vat-pill.pending { background: var(--orange-100); color: var(--orange-700); }
				.packing-vat-lines { display: grid; gap: 6px; }
				.packing-vat-line { display: flex; justify-content: space-between; }
				.packing-vat-line span:first-child { color: var(--text-muted); }
				@media (max-width: 768px) {
					.packing-vat-sides { grid-template-columns: 1fr; }
					.packing-vat-side + .packing-vat-side { border-left: 0; border-top: 1px solid var(--border-color); }
				}
			</style>
			<div class="packing-vat-help">${__("Check the inclusive/exclusive decision for purchase and selling. Open a packing row to change the mode or VAT rate.")}</div>
			${cards}
		`;
	}

	function getPackingVatSideHtml(row, direction) {
		const fields = packingVatFields[direction];
		const confirmed = cint(row[fields.confirmed]);
		const pillClass = confirmed || !flt(row[fields.rate]) ? "ok" : "pending";

		return `
			<div class="packing-vat-side">
				<div class="packing-vat-side__title">
					<strong>${fields.label}</strong>
					<span class="packing-vat-pill ${pillClass}">${escapeHtml(row[fields.status] || "")}</span>
				</div>
				<div class="packing-vat-lines">
					<div class="packing-vat-line"><span>${__("Entered Rate")}</span><strong>${formatCurrency(row[fields.entry])}</strong></div>
					<div class="packing-vat-line"><span>${__("VAT Mode")}</span><strong>${escapeHtml(row[fields.mode] || "Excluding VAT")}</strong></div>
					<div class="packing-vat-line"><span>${__("Rate Excl. VAT")}</span><strong>${formatCurrency(row[fields.net])}</strong></div>
					<div class="packing-vat-line"><span>${__("VAT Amount")}</span><strong>${formatCurrency(row[fields.vat])}</strong></div>
					<div class="packing-vat-line"><span>${__("Rate Incl. VAT")}</span><strong>${formatCurrency(row[fields.gross])}</strong></div>
				</div>
			</div>
		`;
	}

	function formatCurrency(value) {
		return format_currency(flt(value), frappe.defaults.get_default("currency"));
	}

	function escapeHtml(value) {
		if (frappe.utils?.escape_html) return frappe.utils.escape_html(String(value || ""));
		return String(value || "").replace(/[&<>"']/g, (char) => ({
			"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
		})[char]);
	}

	function setupArabicItemNameField(frm) {
		const field = frm.fields_dict[arabicItemNameField];
		if (!field) return;
		frm._arabic_item_name_auto_value = frm._arabic_item_name_auto_value || "";
		if (field.$input) field.$input.attr("dir", "rtl").css("text-align", "right");
		addArabicFieldButton(frm);
		if (!frm.doc[arabicItemNameField]) queueArabicItemNameTranslation(frm);
	}

	function addArabicTranslationButton(frm) {
		if (!frm.fields_dict[arabicItemNameField]) return;
		frm.add_custom_button(__("Translate Arabic"), () => {
			frm._arabic_item_name_touched = false;
			translateArabicItemName(frm, true);
		}, __("Retail"));
	}

	function addArabicFieldButton(frm) {
		const field = frm.fields_dict[arabicItemNameField];
		if (!field || field._arabic_translate_button_added || !field.$wrapper) return;
		field._arabic_translate_button_added = true;

		const button = $(`<button class="btn btn-xs btn-default" type="button" style="margin-top: 6px;">
			${__("Translate Arabic")}
		</button>`);
		button.on("click", () => {
			frm._arabic_item_name_touched = false;
			translateArabicItemName(frm, true);
		});
		field.$wrapper.append(button);
	}

	function queueArabicItemNameTranslation(frm) {
		if (!frm.fields_dict[arabicItemNameField]) return;

		clearTimeout(frm._arabic_item_name_timer);
		frm._arabic_item_name_timer = setTimeout(() => {
			translateArabicItemName(frm);
		}, arabicTranslationDelay);
	}

	function translateArabicItemName(frm, showFeedback = false) {
		const sourceText = getArabicTranslationSource(frm);
		const currentArabic = (frm.doc[arabicItemNameField] || "").trim();
		const lastAutoValue = (frm._arabic_item_name_auto_value || "").trim();
		const manuallyChanged = frm._arabic_item_name_touched && currentArabic && currentArabic !== lastAutoValue;
		if (!sourceText) {
			if (showFeedback) frappe.show_alert({ message: __("Enter Item Name first"), indicator: "orange" });
			return;
		}
		if (manuallyChanged) {
			if (showFeedback) frappe.show_alert({ message: __("Arabic name was manually changed"), indicator: "orange" });
			return;
		}

		frm._arabic_item_name_source = sourceText;
		frappe.call({
			method: "retail.domains.item.arabic_name.translate_item_name_to_arabic",
			args: { text: sourceText },
			freeze: false,
			callback: ({ message }) => {
				if (!message || frm._arabic_item_name_source !== getArabicTranslationSource(frm)) return;
				if (message.configured === false) {
					showArabicTranslationConfigOnce(frm);
					return;
				}
				if (message.error) {
					showArabicTranslationErrorOnce(frm);
					return;
				}
				if (!message.translated_text) return;

				frm._arabic_item_name_auto_value = message.translated_text;
				frm._arabic_item_name_touched = false;
				frm._setting_arabic_item_name = true;
				Promise.resolve(frm.set_value(arabicItemNameField, message.translated_text)).finally(() => {
					frm._setting_arabic_item_name = false;
				});
				if (showFeedback) frappe.show_alert({ message: __("Arabic translated"), indicator: "green" });
			},
			error: () => showArabicTranslationErrorOnce(frm),
		});
	}

	function getArabicTranslationSource(frm) {
		return (frm.doc.item_name || frm.doc.item_code || "").trim();
	}

	function showArabicTranslationConfigOnce(frm) {
		if (frm._arabic_item_name_config_shown) return;
		frm._arabic_item_name_config_shown = true;
		frappe.show_alert({ message: __("Arabic translation service not configured"), indicator: "orange" });
	}

	function showArabicTranslationErrorOnce(frm) {
		if (frm._arabic_item_name_error_shown) return;
		frm._arabic_item_name_error_shown = true;
		frappe.show_alert({ message: __("Arabic translation failed"), indicator: "orange" });
	}

	function refreshMargin(frm) {
		const sellingNet = getSellingNetRate(frm);
		const costNet = getCostNetRate(frm);
		const margin = sellingNet ? sellingNet - costNet : 0;
		const marginPercent = sellingNet ? (margin / sellingNet) * 100 : 0;

		setValuesIfChanged(frm.doc, "Item", frm.doc.name, {
			custom_margin: flt(margin, 2),
			custom_margin_: flt(marginPercent, 3),
		});
	}

	function setValuesIfChanged(doc, doctype, name, values) {
		const changed = {};
		Object.keys(values || {}).forEach((fieldname) => {
			const current = doc ? doc[fieldname] : undefined;
			const next = values[fieldname];
			if (flt(current) !== flt(next) && current !== next) {
				changed[fieldname] = next;
			}
		});
		if (!Object.keys(changed).length) return Promise.resolve();
		return frappe.model.set_value(doctype, name, changed);
	}

	function getSellingNetRate(frm) {
		if (flt(frm.doc.custom_sales_rate_entry) > 0) {
			return flt(frm.doc.custom_sales_net_rate);
		}
		return flt(frm.doc.standard_rate);
	}

	function getCostNetRate(frm) {
		if (frm.doc.custom_purchase_rate_entry !== undefined
			&& frm.doc.custom_purchase_rate_entry !== null
			&& frm.doc.custom_purchase_rate_entry !== "") {
			return flt(frm.doc.custom_purchase_net_rate);
		}
		return flt(
			frm.doc.custom_default_purchase_rate
			|| frm.doc.last_purchase_rate
			|| frm.doc.valuation_rate
			|| frm.doc.custom_average_purchase_rate
		);
	}

	function removeEmptyBarcodeRows(frm) {
		if (!Array.isArray(frm.doc.barcodes)) return;
		let removed = false;
		for (let index = frm.doc.barcodes.length - 1; index >= 0; index--) {
			const row = frm.doc.barcodes[index];
			if (row.barcode) continue;
			if (row.doctype && row.name) frappe.model.clear_doc(row.doctype, row.name);
			frm.doc.barcodes.splice(index, 1);
			removed = true;
		}
		if (removed) frm.refresh_field("barcodes");
	}

	function hasEnteredValue(value) {
		return value !== undefined && value !== null && value !== "";
	}
})();

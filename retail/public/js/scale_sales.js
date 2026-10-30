/* Scale labels are decoded only for checked Item masters by the server. */
(() => {
	frappe.provide("retail.scale_sales");
	const sales = new Set(["Sales Invoice", "Sales Order", "Delivery Note", "Quotation", "POS Invoice"]);
	function preparePrecision(frm) {
		const child = frm.fields_dict.items.grid.doctype;
		for (const field of ["qty", "rate", "price_list_rate"]) {
			const df = frappe.meta.get_docfield(child, field, frm.doc.name);
			if (df) df.precision = 9;
		}
	}

	async function finishItemLookups() {
		// Core qty/uom handlers launch pricing work without returning its promise.
		// Let their serial tasks and chained requests finish before label pricing.
		do {
			await frappe.after_ajax();
			await new Promise(resolve => setTimeout(resolve, 0));
		} while (frappe.request.ajax_count);
	}

	retail.scale_sales.apply = async function (frm, row, label) {
		if (frm.doc.docstatus !== 0) frappe.throw(__("Scale labels can only be applied to draft sales."));
		await finishItemLookups();
		preparePrecision(frm);
		let qty = label.scale_qty;
		// Only encoded monetary values are VAT-inclusive; ordinary weight/quantity
		// labels continue to use the existing transaction rate unchanged.
		let vatFactor = 1;
		if (label.scale_rate != null || label.scale_amount != null) {
			const {message: vatRate} = await frappe.call({
				method: "retail.domains.transactions.vat.get_transaction_item_vat_rate",
				args: {item_code: row.item_code, child_doctype: row.doctype,
					parent_doctype: frm.doc.doctype, transaction_type: frm.doc.transaction_type,
					item_tax_template: row.item_tax_template},
			});
			vatFactor += flt(vatRate) / 100;
		}
		let rate = label.scale_rate == null ? flt(row.rate) : label.scale_rate / vatFactor;
		const amount = label.scale_amount == null ? null : label.scale_amount / vatFactor;
		if (qty == null) {
			qty = rate ? amount / rate : 1;
			if (!rate) rate = amount;
		} else if (amount != null) {
			rate = amount / qty;
		} else if (!rate && label.scale_rate == null) {
			rate = await new Promise((resolve, reject) => {
				const dialog = frappe.prompt({fieldname: "rate", label: __("Selling Rate"),
					fieldtype: "Currency", reqd: 1}, values => {
					if (flt(values.rate) <= 0) { reject(new Error(__("Enter a positive selling rate."))); return; }
					resolve(flt(values.rate));
				}, __("Enter New Price"));
				dialog.$wrapper.on("hidden.bs.modal", () => reject(new Error(__("Scale sale cancelled."))));
			});
		}
		await frappe.model.set_value(row.doctype, row.name, "qty", frm.doc.is_return ? -qty : qty);
		await finishItemLookups();
		// Apply the VAT-exclusive rate after quantity pricing completes. Existing
		// VAT handlers calculate tax and the inclusive display fields normally.
		await frappe.model.set_value(row.doctype, row.name, {
			price_list_rate: rate, discount_percentage: 0, discount_amount: 0,
			margin_type: "", margin_rate_or_amount: 0, rate_with_margin: 0, rate,
			amount: (frm.doc.is_return ? -qty : qty) * rate,
		});
		// Identity was already resolved by the scale lookup. Triggering barcode
		// again invokes the standard lookup, which asynchronously resets qty to 1.
		row.barcode = label.barcode;
		await frm.cscript.calculate_taxes_and_totals();
		frm.refresh_field("items");
	};

	function install() {
		const prototype = window.erpnext?.utils?.BarcodeScanner?.prototype;
		if (!prototype || prototype.__retail_scale_sales) return;
		prototype.__retail_scale_sales = true;
		const scan = prototype.scan_api_call;
		prototype.scan_api_call = function (input, callback) {
			if (!sales.has(this.frm.doc.doctype) || !["erpnext.stock.utils.scan_barcode",
				"retail.domains.item.packing_scan.scan_barcode"].includes(this.scan_api)) {
				return scan.call(this, input, callback);
			}
			return frappe.call({method: "retail.domains.item.packing_scan.scan_barcode",
				args: {search_value: input, ctx: {set_warehouse: this.frm.doc.set_warehouse,
					company: this.frm.doc.company}}}).then(callback);
		};
		const update = prototype.update_table;
		prototype.update_table = async function (data) {
			if (!sales.has(this.frm.doc.doctype) || !data.scale_barcode_type) return update.call(this, data);
			if (this.frm.doc.docstatus !== 0 || this.dont_allow_new_row) {
				frappe.throw(__("Add scale labels to an editable sales document."));
			}
			const grid = this.frm.fields_dict[this.items_table_name].grid;
			const row = (this.frm.doc[this.items_table_name] || []).find(item => !item.item_code) ||
				frappe.model.add_child(this.frm.doc, grid.doctype, this.items_table_name);
			await this.frm.script_manager.trigger(`${this.items_table_name}_add`, row.doctype, row.name);
			await this.set_warehouse(row);
			await frappe.model.set_value(row.doctype, row.name, "item_code", data.item_code);
			await frappe.model.set_value(row.doctype, row.name, "uom", data.uom);
			await retail.scale_sales.apply(this.frm, row, data);
			this.clean_up();
			return row;
		};
	}
	install();
	$(document).on("startup", install);
	for (const doctype of sales) frappe.ui.form.on(doctype, {setup: install, async refresh(frm) {
		install();
		if (frm.doc.docstatus !== 0) return;
		for (const row of frm.doc.items || []) {
			if (!/^\d{13}$|^\d{18}$/.test(row.barcode || "")) continue;
			const {message} = await frappe.call({method: "retail.domains.item.packing_scan.scan_barcode",
				args: {search_value: row.barcode}});
			if (message?.scale_barcode_type && message.item_code === row.item_code) {
				preparePrecision(frm);
				break;
			}
		}
	}});
})();

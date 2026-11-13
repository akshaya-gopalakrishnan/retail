// Item-only layout and barcode previews; saving retains the existing Item hooks.
(() => {
	frappe.ui.form.ItemQuickEntryForm = class extends frappe.ui.form.RetailQuickEntryForm {
		set_meta_and_mandatory_fields() {
			super.set_meta_and_mandatory_fields();
			const fields = this.mandatory.map((df) => ({ ...df }));
			// Keep site-selected fields, splitting the long single column evenly.
			const midpoint = Math.ceil(fields.length / 2);
			this.mandatory = [
				{ fieldtype: "Section Break", fieldname: "retail_item_details" },
				...fields.slice(0, midpoint),
				{ fieldtype: "Column Break", fieldname: "retail_item_column" },
				...fields.slice(midpoint),
			];
		}

		render_dialog() {
			super.render_dialog();
			this.dialog.$wrapper.find(".modal-dialog").css({
				width: "960px",
				"max-width": "calc(100vw - 32px)",
			});
			this.align_rate_checkboxes();
			const scale = this.dialog.fields_dict.custom_scale_item;
			if (scale) {
				const onchange = scale.df.onchange;
				scale.df.onchange = (...args) => {
					if (this.resetting) return;
					onchange?.apply(scale, args);
					return this.generate_barcode(true);
				};
			}
			this.vat_defaults_ready = this.apply_company_vat_defaults();
			this.generate_barcode();
		}

		align_rate_checkboxes() {
			for (const [rateName, checkName] of [
				["custom_purchase_rate_entry", "custom_purchase_rate_includes_vat"],
				["custom_sales_rate_entry", "custom_sales_rate_includes_vat"],
			]) {
				const rate = this.dialog.fields_dict[rateName];
				const check = this.dialog.fields_dict[checkName];
				if (!rate || !check) continue;
				const heading = rate.$wrapper.find(".clearfix").first();
				if (!heading.length) continue;
				heading.css({display: "flex", "align-items": "center", "justify-content": "space-between", gap: "8px", "flex-wrap": "wrap"});
				check.$wrapper.appendTo(heading).css({"margin-bottom": 0});
				check.$wrapper.find(".checkbox, label").css({"margin-top": 0, "margin-bottom": 0});
			}
		}

		async insert() {
			await this.vat_defaults_ready;
			return super.insert();
		}

		async save_and_new(close_after_save = false) {
			await this.vat_defaults_ready;
			return super.save_and_new(close_after_save);
		}

		async apply_company_vat_defaults() {
			const dialog = this.dialog;
			if (!dialog.doc.__islocal || dialog.doc.__retail_vat_defaults_applied) return;
			dialog.doc.__retail_vat_defaults_applied = true;
			const before = Object.fromEntries(["custom_tax", "custom_purchase_tax_template", "custom_purchase_rate_includes_vat", "custom_sales_rate_includes_vat"].map(field => [field, dialog.fields_dict[field] ? dialog.get_value(field) : dialog.doc[field]]));
			const {message} = await frappe.call({method: "retail.domains.item.vat_pricing.get_company_item_vat_defaults"});
			for (const [field, value] of Object.entries(message || {})) {
				const current = dialog.fields_dict[field] ? dialog.get_value(field) : dialog.doc[field];
				if ((field.endsWith("_includes_vat") || !before[field]) && current === before[field]) {
					if (dialog.fields_dict[field]) await dialog.set_value(field, value);
					else dialog.doc[field] = value;
				}
			}
		}

		async generate_barcode(force = false) {
			const dialog = this.dialog;
			if (!dialog.fields_dict.custom_barcode) return;
			const generation = (this.barcode_generation = (this.barcode_generation || 0) + 1);
			const previous = dialog.get_value("custom_barcode");
			if (!force && previous) return;
			const scale = Number(dialog.get_value("custom_scale_item")) === 1;
			if (dialog.fields_dict.custom_scale_barcode_type) {
				await dialog.set_value(
					"custom_scale_barcode_type",
					scale ? dialog.get_value("custom_scale_barcode_type") || "Weight" : ""
				);
			}
			const { message } = await frappe.call({
				method: "retail.api.scale_item_api.preview_scale_barcode",
				args: { scale_item: scale ? 1 : 0 },
			});
			if (
				generation !== this.barcode_generation ||
				(Number(dialog.get_value("custom_scale_item")) === 1) !== scale ||
				dialog.get_value("custom_barcode") !== previous
			)
				return;
			dialog.doc.__retail_scale_barcode_preview = scale ? message : null;
			dialog.doc.__retail_normal_barcode_preview = scale ? null : message;
			await dialog.set_value("custom_barcode", message);
		}
	};
})();

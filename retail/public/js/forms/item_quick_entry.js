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
			const scale = this.dialog.fields_dict.custom_scale_item;
			if (scale) {
				const onchange = scale.df.onchange;
				scale.df.onchange = (...args) => {
					if (this.resetting) return;
					onchange?.apply(scale, args);
					return this.generate_barcode(true);
				};
			}
			this.generate_barcode();
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
			if (!scale) {
				dialog.doc.__retail_scale_barcode_preview = null;
				await dialog.set_value(
					"custom_barcode",
					String(1000000000000 + Math.floor(Math.random() * 9000000000000))
				);
				return;
			}
			const { message } = await frappe.call({
				method: "retail.api.scale_item_api.preview_scale_barcode",
			});
			if (
				generation !== this.barcode_generation ||
				!Number(dialog.get_value("custom_scale_item")) ||
				dialog.get_value("custom_barcode") !== previous
			)
				return;
			dialog.doc.__retail_scale_barcode_preview = message;
			await dialog.set_value("custom_barcode", message);
		}
	};
})();

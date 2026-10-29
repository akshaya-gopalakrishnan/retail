// Keep derived Batch values read-only while showing them in Quick Entry.
(() => {
	frappe.ui.form.BatchQuickEntryForm = class extends frappe.ui.form.QuickEntryForm {
		set_meta_and_mandatory_fields() {
			super.set_meta_and_mandatory_fields();
			for (const fieldname of ["stock_uom"]) {
				const df = this.meta.fields.find(field => field.fieldname === fieldname);
				if (df?.allow_in_quick_entry && !this.mandatory.some(field => field.fieldname === fieldname)) {
					this.mandatory.push({ ...df, read_only: 1 });
				}
			}
		}

		render_dialog() {
			super.render_dialog();
			const item = this.dialog.fields_dict.item;
			if (!item) return;
			const onchange = item.df.onchange;
			item.df.onchange = (...args) => {
				onchange?.apply(item, args);
				return this.update_item_defaults();
			};
			this.update_item_defaults();
		}

		async update_item_defaults() {
			const item = this.dialog.get_value("item");
			const generation = this.__item_generation = (this.__item_generation || 0) + 1;
			for (const field of ["stock_uom"]) {
				if (this.dialog.fields_dict[field]) await this.dialog.set_value(field, null);
			}
			if (!item) return;
			const result = await frappe.call({
				method: "retail.batch_quick_entry.get_item_defaults",
				args: { item },
			});
			if (generation !== this.__item_generation || this.dialog.get_value("item") !== item) return;
			for (const [field, value] of Object.entries(result.message || {})) {
				if (this.dialog.fields_dict[field]) await this.dialog.set_value(field, value);
			}
		}
	};
})();

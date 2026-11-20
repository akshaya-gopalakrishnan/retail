// Common form actions. Document controllers retain their native save lifecycle.
(() => {
	// Opt in custom entry dialogs without replacing their primary actions.
	retail.keyboard.bind_dialog = (dialog) => {
		if (dialog.__retail_navigation) return;
		dialog.__retail_navigation = true;
		const shared = frappe.ui.form.RetailQuickEntryForm.prototype;
		const navigation = {
			dialog,
			commit_field: shared.commit_field,
			keyboard_fields() {
				const controls = Object.values(dialog.fields_dict);
				for (const field of Object.values(dialog.fields_dict)) {
					for (const row of field.grid?.grid_rows || []) {
						controls.push(...Object.values(row.on_grid_fields_dict || {}));
						controls.push(...Object.values(row.grid_form?.fields_dict || {}));
					}
				}
				return shared.keyboard_fields.call({dialog: {fields_dict: controls}});
			},
		};
		dialog.$wrapper[0].addEventListener("keydown", (event) => {
			if (event.isComposing || event.ctrlKey || event.metaKey || event.altKey || dialog.working ||
				window.cur_dialog !== dialog || event.target.matches("textarea,button,a,[contenteditable=true]") ||
				!["Enter", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) return;
			const field = navigation.keyboard_fields().find((f) => f.$input[0] === event.target);
			if (!field || (event.shiftKey && event.key !== "Enter")) return;
			if (field.awesomplete?.opened && ["ArrowUp", "ArrowDown", "Enter"].includes(event.key)) return;
			if ($(".datepicker.active:visible").length) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			if (event.repeat) return;
			shared.move_field.call(navigation, field, event.key, event.shiftKey).catch(console.error);
		}, true);
	};
	const Base = frappe.ui.form.QuickEntryForm.prototype;
	const render = Base.render_dialog;
	Base.render_dialog = function (...args) {
		const result = render.apply(this, args);
		if (this instanceof frappe.ui.form.RetailQuickEntryForm) return result;
		const shared = frappe.ui.form.RetailQuickEntryForm.prototype;
		for (const name of ["keyboard_fields", "commit_field", "move_field"])
			if (!this[name]) this[name] = shared[name];
		this.dialog.$wrapper[0].addEventListener("keydown", (event) => {
			if (event.isComposing || window.cur_dialog !== this.dialog) return;
			const field = this.keyboard_fields().find((f) => f.$input[0] === event.target);
			if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
				event.preventDefault();
				event.stopImmediatePropagation();
				if (this.dialog.working || this.__shortcut_busy) return;
				this.__shortcut_busy = true;
				Promise.resolve(this.commit_field(field)).then(() => {
					if (!this.dialog.get_values()) return;
					// Never activate a Submit action through a save shortcut.
					if (this.dialog.get_primary_btn().text().trim() !== __("Save")) return;
					if (!event.shiftKey) {
						this.dialog.get_primary_btn().trigger("click");
						return;
					}
					const open = this.open_form_if_not_list;
					this.open_form_if_not_list = () => {};
					this.dialog.working = true;
					return Promise.resolve(this.insert()).then((doc) => {
						if (doc?.name && !doc.__islocal)
							return frappe.ui.form.make_quick_entry(this.doctype, this.after_insert, this.init_callback, null, this.force);
					}).finally(() => { this.open_form_if_not_list = open; });
				}).finally(() => { this.__shortcut_busy = false; });
				return;
			}
			if (!field || event.ctrlKey || event.metaKey || event.altKey ||
				!["Enter", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key) ||
				event.target.matches("textarea,select") || field.awesomplete?.opened) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			this.move_field(field, event.key, event.shiftKey);
		}, true);
		return result;
	};

	document.addEventListener("keydown", (event) => {
		if (event.isComposing || event.repeat) return;
		const saveNew = (event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "s";
		const addRow = event.altKey && !event.ctrlKey && !event.metaKey && event.key === "Enter";
		if (!saveNew && !addRow) return;
		const dialog = window.cur_dialog;
		const frm = window.cur_frm;
		if (saveNew && dialog) return; // Quick Entry owns its save handler.
		if (!dialog && (!frm || frappe.get_route()[0] !== "Form")) return;
		event.preventDefault();
		event.stopImmediatePropagation();
		if (addRow) {
			const fields = dialog?.fields_dict || frm.fields_dict;
			const grids = Object.values(fields).map((f) => f.grid).filter((g) =>
				g && !g.df.read_only && !g.df.cannot_add_rows && $(g.wrapper).is(":visible"));
			const grid = grids.find((g) => g.wrapper[0].contains(event.target)) || grids.find((g) => g.df.fieldname === "items") || grids[0];
			if (grid?.is_editable()) grid.add_new_row(null, null, true, null, true);
			return;
		}
		if (frm.doc.docstatus !== 0 || frm.__shortcut_saving || !frm.perm?.some((p) => p.write || (frm.is_new() && p.create))) return;
		frm.__shortcut_saving = true;
		Promise.resolve().then(() => {
			document.activeElement?.blur();
			return frm.save();
		}).then(() => {
			if (!frm.is_dirty() && !frm.is_new()) return frappe.new_doc(frm.doctype);
		}).finally(() => { frm.__shortcut_saving = false; });
	}, true);
})();

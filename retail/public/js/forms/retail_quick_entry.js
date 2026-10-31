// Keyboard and Save+New behavior for Retail master-data quick-entry popups.
(() => {
	frappe.ui.form.RetailQuickEntryForm = class extends frappe.ui.form.QuickEntryForm {
		render_dialog() {
			super.render_dialog();
			this.empty_values = this.entry_values();
			this.calling_link = frappe._from_link;
			for (const field of Object.values(this.dialog.fields_dict)) {
				if (field.df.fieldtype === "Link")
					field.new_doc = () => this.create_linked_value(field);
			}
			// Keep Frappe's primary action specific to Save despite the matching styling.
			this.dialog.get_primary_btn = () =>
				this.dialog.standard_actions.find(".btn-modal-primary");
			$("<button>", {
				type: "button",
				class: "btn btn-primary btn-sm retail-save-new",
				text: __("Save+New"),
			})
				.on("click", () => this.save_and_new())
				.insertBefore(this.dialog.get_primary_btn());
			this.dialog.$wrapper[0].addEventListener(
				"keydown",
				(event) => this.handle_key(event),
				true
			);
		}
		create_linked_value(field) {
			const calling_link = frappe._from_link;
			frappe._from_link = null;
			frappe.route_options = { name_field: field.get_label_value() };
			// Update the actual dialog control, rather than Frappe's cloned link control.
			return frappe.ui.form.make_quick_entry(
				field.get_options(),
				async (saved) => {
					await field.set_value(saved.name);
					if (frappe.quick_entry?.saving_and_new) return;
					frappe.quick_entry = this;
					frappe._from_link = calling_link;
				},
				(dialog) => {
					dialog.$wrapper.one("hidden.bs.modal", () => {
						frappe.quick_entry = this;
						frappe._from_link = calling_link;
						field.$input?.focus();
					});
					dialog.onhide = () => {
						frappe.quick_entry = this;
						// Native insert dispatches its callback synchronously after hide().
						setTimeout(() => {
							frappe._from_link = calling_link;
						}, 0);
					};
				},
				null,
				true
			);
		}

		keyboard_fields() {
			return Object.values(this.dialog.fields_dict).filter((field) => {
				const input = field.$input?.[0];
				return (
					input &&
					$(input).is(":visible") &&
					!input.disabled &&
					!input.readOnly &&
					!field.df.read_only
				);
			});
		}
		focus_first_field() {
			this.keyboard_fields()[0]?.$input?.focus();
		}
		entry_values() {
			const values = { ...this.dialog.get_values(true) };
			delete values.custom_barcode;
			return JSON.stringify(values);
		}
		async commit_field(field) {
			if (field?.get_input_value) await field.set_value(field.get_input_value());
		}
		async move_field(field, key, backwards = false) {
			await this.commit_field(field);
			if (window.cur_dialog && window.cur_dialog !== this.dialog) return;
			const fields = this.keyboard_fields();
			const index = fields.indexOf(field);
			if (index < 0) return;
			let target;
			if (key !== "Enter") {
				const horizontal = ["ArrowLeft", "ArrowRight"].includes(key);
				const sign = ["ArrowLeft", "ArrowUp"].includes(key) ? -1 : 1;
				const center = (f) => {
					const r = f.$input[0].getBoundingClientRect();
					return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
				};
				const from = center(field);
				const axis = horizontal ? "x" : "y",
					cross = horizontal ? "y" : "x";
				target = fields
					.filter((f) => f !== field)
					.map((f) => {
						const to = center(f),
							distance = (to[axis] - from[axis]) * sign;
						return {
							field: f,
							distance,
							score: distance + Math.abs(to[cross] - from[cross]) * 4,
						};
					})
					.filter((f) => f.distance > 8)
					.sort((a, b) => a.score - b.score)[0]?.field;
				if (!target && horizontal) target = fields[index + sign];
			} else target = fields[index + (backwards ? -1 : 1)];
			field.awesomplete?.close();
			if (target) {
				target.$input[0].focus();
				target.$input[0].select?.();
			} else if (key === "Enter" && !backwards) this.dialog.get_primary_btn().focus();
		}
		handle_key(event) {
			if (event.isComposing) return;
			const field = this.keyboard_fields().find((f) => f.$input[0] === event.target);
			if (
				(event.ctrlKey || event.metaKey) &&
				["s", "enter"].includes(event.key.toLowerCase())
			) {
				event.preventDefault();
				event.stopImmediatePropagation();
				if (this.dialog.working || this.keyboard_busy) return;
				this.keyboard_busy = true;
				this.commit_field(field)
					.then(() =>
						event.key === "Enter" ? this.save_and_close() : this.save_and_new()
					)
					.finally(() => {
						this.keyboard_busy = false;
					});
				return;
			}
			if (this.dialog.working) return;
			if (
				event.key === "Tab" &&
				!event.shiftKey &&
				!event.ctrlKey &&
				!event.metaKey &&
				!event.altKey &&
				field?.df?.fieldtype === "Link" &&
				!field.df.only_select &&
				frappe.model.can_create(field.get_options())
			) {
				event.preventDefault();
				event.stopImmediatePropagation();
				field.awesomplete?.close();
				if (!this.creating_link) {
					this.creating_link = true;
					Promise.resolve(field.new_doc()).finally(() => {
						this.creating_link = false;
					});
				}
				return;
			}

			if (
				!field ||
				event.ctrlKey ||
				event.metaKey ||
				event.altKey ||
				!["Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)
			)
				return;
			if (event.shiftKey && field.$input[0].tagName === "TEXTAREA") return;
			// Suggestion arrows keep their native selection behavior. Enter accepts then advances.
			if (
				field.awesomplete?.opened &&
				["ArrowUp", "ArrowDown", "Enter"].includes(event.key)
			) {
				if (event.key === "Enter")
					setTimeout(() => this.move_field(field, "Enter", event.shiftKey), 0);
				return;
			}
			event.preventDefault();
			event.stopImmediatePropagation();
			this.move_field(field, event.key, event.shiftKey);
		}

		async save_and_close() {
			// Finish an untouched blank next entry without creating another record.
			const name_field = {
				Item: "item_name",
				"Item Group": "item_group_name",
				Brand: "brand",
			}[this.doctype];
			if (
				!this.dialog.working &&
				name_field &&
				!this.dialog.get_value(name_field) &&
				this.entry_values() === this.empty_values
			) {
				this.dialog.hide();
				frappe.model.clear_doc(this.doctype, this.dialog.doc.name);
				return;
			}
			return this.save_and_new(true);
		}

		async save_and_new(close_after_save = false) {
			const dialog = this.dialog;
			if (dialog.working || !dialog.get_values()) return;
			let ready_for_next = false;
			dialog.working = true;
			this.saving_and_new = !close_after_save;
			dialog.set_message(__("Saving..."));
			try {
				this.update_doc();
				const { message: saved } = await frappe.call({
					method: "frappe.client.save",
					args: { doc: dialog.doc },
					freeze: true,
				});
				if (!saved?.name) return;
				frappe.model.clear_doc(this.doctype, dialog.doc.name);
				frappe.model.sync(saved);
				if (this.calling_link) {
					frappe._from_link = this.calling_link;
					frappe.ui.form.update_calling_link(saved);
				} else if (this.after_insert) await this.after_insert(saved);
				if (window.cur_list?.doctype === this.doctype) await cur_list.refresh();
				if (close_after_save) {
					this.doc = dialog.doc = saved;
					dialog.hide();
					frappe.show_alert({
						message: __("{0} saved", [saved.name]),
						indicator: "green",
					});
					return;
				}
				this.resetting = true;
				// A new model restores site defaults without carrying the saved values over.
				this.doc = frappe.model.get_new_doc(this.doctype, null, null, true);
				dialog.doc = this.doc;
				this.barcode_generation = (this.barcode_generation || 0) + 1;
				for (const field of Object.values(dialog.fields_dict)) {
					if (frappe.model.no_value_type.includes(field.df.fieldtype)) continue;
					field.docname = this.doc.name;
					await dialog.set_value(
						field.df.fieldname,
						this.doc[field.df.fieldname] ?? null
					);
				}
				this.resetting = false;
				dialog.refresh_dependency();
				await this.generate_barcode?.();
				this.empty_values = this.entry_values();
				ready_for_next = true;
				frappe.show_alert({ message: __("{0} saved", [saved.name]), indicator: "green" });
			} finally {
				this.resetting = false;
				this.saving_and_new = false;
				dialog.working = false;
				dialog.clear_message();
				if (ready_for_next) this.focus_first_field();
			}
		}
	};
	for (const name of ["ItemGroup", "Brand"]) {
		frappe.ui.form[name + "QuickEntryForm"] = class extends (
			frappe.ui.form.RetailQuickEntryForm
		) {};
	}
})();

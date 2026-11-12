/* Quick Entry edits the real document; all prices and quantities use native purchase handlers. */
(() => {
	const esc = value => frappe.utils.escape_html(String(value ?? ""));
	const editable = frm => frm.doc.docstatus === 0 && !frm.doc.is_return && frm.perm?.[0]?.write;
	function focusFirstEditable(root) {
		const input = root && Array.from(root.querySelectorAll("input, textarea, select")).find(field =>
			!field.disabled && !field.readOnly && !["hidden", "checkbox", "button", "submit"].includes(field.type) &&
			field.tabIndex !== -1 && field.getClientRects().length);
		if (!input) return false;
		input.focus();
		input.scrollIntoView?.({block: "nearest", inline: "nearest"});
		if (input.tagName === "INPUT" && typeof input.select === "function") input.select();
		return true;
	}
	function bindItemRowEnter(root, rowSelector, allowed, addRow, focusScan) {
		if (!root || root.__retail_row_enter) return;
		root.__retail_row_enter = true;
		root.addEventListener("keydown", event => {
			const arrows = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];
			if (arrows.includes(event.key) && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey &&
				!event.isComposing && allowed()) {
				const input = event.target, row = input.closest(rowSelector);
				if (!row || !input.matches("input, textarea, select") || input.getAttribute("aria-expanded") === "true" ||
					$(input).closest(".awesomplete").find("ul:visible").length) return;
				const fieldsFor = element => Array.from(element.querySelectorAll("input, textarea, select")).filter(field =>
					!field.disabled && !field.readOnly && !["hidden", "button", "submit"].includes(field.type) &&
					!field.matches(".grid-row-check, .quick-receipt-select") && field.getClientRects().length);
				const fields = fieldsFor(row), index = fields.indexOf(input);
				if (index < 0) return;
				event.preventDefault();
				event.stopImmediatePropagation();
				let next;
				if (["ArrowLeft", "ArrowRight"].includes(event.key)) next = fields[index + (event.key === "ArrowLeft" ? -1 : 1)];
				else {
					const rows = Array.from(root.querySelectorAll(rowSelector)).filter(element => element.getClientRects().length);
					const nextRow = rows[rows.indexOf(row) + (event.key === "ArrowUp" ? -1 : 1)];
					if (nextRow) {
						// Full-form controls are created when the row enters edit mode.
						$(nextRow).data("grid_row")?.toggle_editable_row(true);
						const candidates = fieldsFor(nextRow);
						const name = input.getAttribute("data-fieldname");
						next = (name && candidates.find(field => field.getAttribute("data-fieldname") === name)) || candidates[index];
					}
				}
				if (next) {
					next.focus();
					next.scrollIntoView?.({block: "nearest", inline: "nearest"});
				}
				return;
			}
			if (event.key === "Tab" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey &&
				!event.isComposing && allowed() && focusScan && event.target.closest(rowSelector)) {
				event.preventDefault();
				event.stopImmediatePropagation();
				focusScan();
				return;
			}
			if (event.key !== "Enter" || event.altKey || event.ctrlKey || event.metaKey || event.isComposing || !allowed()) return;
			const input = event.target;
			// Serial numbers keep multiline entry; Link suggestions keep native selection.
			if (!input.matches("input:not([type=button]), select") ||
				input.getAttribute("aria-expanded") === "true" ||
				$(input).closest(".awesomplete").find("ul:visible").length) return;
			const row = input.closest(rowSelector);
			if (!row) return;
			const inputs = Array.from(row.querySelectorAll("input, select")).filter(field =>
				!field.disabled && !field.readOnly && field.type !== "hidden" &&
				!field.matches(".grid-row-check, .quick-receipt-select, [type=submit]") &&
				field.type !== "button" && field.tabIndex !== -1 && field.getClientRects().length);
			const index = inputs.indexOf(input);
			if (index < 0) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			if (event.repeat) return;
			const next = inputs[index + (event.shiftKey ? -1 : 1)];
			if (next) {
				next.focus(); // Blur commits through the existing field handlers.
				if (next.tagName === "INPUT" && next.type !== "checkbox" && typeof next.select === "function") next.select();
			} else if (!event.shiftKey && addRow) {
				input.blur();
				addRow();
			}
		}, true);
	}
	const shortcutHelp = () => __("Alt+Q: Quick Entry · Alt+A: Add row / selected item · Alt+I: Item search · Alt+B: Barcode · Alt+S: Supplier · Alt+W: Warehouse");
	function shortcutKey(event) {
		if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.repeat || event.isComposing) return;
		const key = event.key.toLowerCase();
		return ["q", "a", "i", "b", "s", "w"].includes(key) ? key : undefined;
	}
	function bindFormShortcuts(frm) {
		bindItemRowEnter(frm.fields_dict.items?.grid?.wrapper?.[0], ".grid-row", () =>
			editable(frm) && window.cur_frm === frm && !$(".modal:visible").length,
			() => frm.fields_dict.items.grid.wrapper.find(".grid-add-row:visible").first().trigger("click"),
			() => frm.fields_dict.scan_barcode?.set_focus());
		if (!frm.wrapper || frm.__retail_purchase_shortcuts) return;
		frm.__retail_purchase_shortcuts = true;
		frm.wrapper.addEventListener("keydown", event => {
			const key = shortcutKey(event);
			if (!key || !editable(frm) || window.cur_frm !== frm || $(".modal:visible").length) return;
			const fields = {s: "supplier", w: "set_warehouse", b: "scan_barcode"};
			const grid = frm.fields_dict.items?.grid;
			if (fields[key] && !frm.fields_dict[fields[key]]?.$input?.is(":visible")) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			if (key === "q") open(frm);
			else if (key === "a") grid?.wrapper.find(".grid-add-row:visible").first().trigger("click");
			else if (key === "i") {
				open(frm);
				frm.__quick_receipt.dialog.get_field("item").set_focus();
			} else frm.fields_dict[fields[key]]?.set_focus();
		});
	}
	function resizeSerial(control) {
		const input = control?.$input?.[0];
		if (input?.tagName !== "TEXTAREA" || !input.getClientRects().length) return;
		input.style.height = "0px";
		const style = window.getComputedStyle(input);
		const border = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
		input.style.height = Math.max(32, input.scrollHeight + border) + "px";
	}
	for (const doctype of ["Purchase Receipt", "Purchase Invoice"]) frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (!editable(frm)) return;
			frm.add_custom_button(__("Quick Entry"), () => open(frm));
			frm.custom_buttons?.[__("Quick Entry")]?.attr("title", shortcutHelp());
			bindFormShortcuts(frm);
			if (frm.is_new() && frappe.flags[quickEntryFlag(frm.doc.doctype)]) {
				delete frappe.flags[quickEntryFlag(frm.doc.doctype)];
				open(frm);
			}
		},
		on_submit(frm) {
			if (!frm.__quick_receipt_next) return;
			const defaults = frm.__quick_receipt_next;
			delete frm.__quick_receipt_next;
			if (frm.__quick_receipt) frm.__quick_receipt.submitting = false;
			frm.__quick_receipt?.dialog.hide();
			frappe.flags[quickEntryFlag(frm.doc.doctype)] = true;
			return frappe.new_doc(frm.doc.doctype, defaults);
		},
	});
	function focusPurchaseRow(frm, cdt, cdn) {
		// A scanner wedge types into whichever input has focus. Leave the cursor
		// on the barcode field until that scan has finished refreshing the row.
		if (!editable(frm) || window.cur_frm !== frm || $(".modal:visible").length || frm.__retail_purchase_scan_active) return;
		clearTimeout(frm.__retail_purchase_focus_timer);
		// Item selection and barcode scans refresh the row after it is created.
		// Wait for those callbacks before resolving the live grid row.
		frm.__retail_purchase_focus_timer = setTimeout(() => {
			frappe.after_ajax(() => {
				if (!editable(frm) || window.cur_frm !== frm || $(".modal:visible").length) return;
				const row = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[cdn];
				if (!row) return;
				row.toggle_editable_row(true);
				focusFirstEditable(row.row?.[0]);
			});
		}, 160);
	}
	for (const doctype of ["Purchase Receipt Item", "Purchase Invoice Item"]) frappe.ui.form.on(doctype, {
		items_add: focusPurchaseRow,
		item_code: focusPurchaseRow,
		barcode: focusPurchaseRow,
	});

	function quickEntryFlag(doctype) {
		return doctype === "Purchase Invoice" ? "retail_new_pi_quick_entry" : "retail_new_pr_quick_entry";
	}

	function bindSupplierTab(field, action) {
		if (!field?.$input?.[0]) return;
		field.__retail_supplier_tab_action = action;
		if (field.__retail_supplier_tab_input === field.$input[0]) return;
		field.__retail_supplier_tab_input = field.$input[0];
		field.$input[0].addEventListener("keydown", event => {
			if (event.key !== "Tab" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
			if (!frappe.model.can_create("Supplier")) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			field.__retail_supplier_tab_action();
		}, true);
	}

	function open(frm) {
		if (frm.__quick_receipt?.dialog.$wrapper.is(":visible")) return;
		frm.__quick_receipt?.dialog.$wrapper.remove();
		const entry = new QuickReceipt(frm);
		frm.__quick_receipt = entry;
		entry.dialog.show();
		entry.render();
		entry.enqueue(async () => { if (await entry.loadItems()) entry.render(); });
		entry.dialog.get_field("scan").set_focus();
	}

	class QuickReceipt {
		constructor(frm) {
			this.frm = frm;
			this.isInvoice = frm.doc.doctype === "Purchase Invoice";
			this.queue = Promise.resolve();
			this.pending = 0;
			this.items = new Map();
			this.selectedRows = new Set();
			this.dialog = new frappe.ui.Dialog({
				title: __(this.isInvoice ? "Quick Purchase Invoice" : "Quick Purchase Receipt"), size: "extra-large",
				fields: [
					{fieldname: "supplier", fieldtype: "Link", options: "Supplier", label: __("Supplier"), reqd: 1,
						default: frm.doc.supplier, onchange: () => this.header("supplier")},
					{fieldtype: "Column Break"},
					{fieldname: "set_warehouse", fieldtype: "Link", options: "Warehouse", label: __(this.isInvoice ? "Warehouse" : "Accepted Warehouse"), reqd: !this.isInvoice || Boolean(Number(frm.doc.update_stock)),
						default: frm.doc.set_warehouse, get_query: () => ({filters: {company: frm.doc.company, is_group: 0}}),
						onchange: () => this.header("set_warehouse")},
					{fieldtype: "Section Break"},
					...(this.isInvoice ? [
						{fieldname: "update_stock", fieldtype: "Check", label: __("Update Stock"),
							default: frm.doc.update_stock, onchange: () => this.header("update_stock")},
						{fieldtype: "Column Break"},
					] : []),
					{fieldname: "custom_update_item_master_rates", fieldtype: "Check", label: __("Update Item Master Rates"),
						default: frm.doc.custom_update_item_master_rates, onchange: () => this.header("custom_update_item_master_rates")},
					{fieldtype: "Column Break"},
					{fieldname: "posting_date", fieldtype: "Date", label: __("Date"), reqd: 1,
						default: frm.doc.posting_date, onchange: () => this.header("posting_date")},
					{fieldtype: "Section Break"},
					...(this.isInvoice ? [
						{fieldname: "bill_no", fieldtype: "Data", label: __("Supplier Invoice No"),
							default: frm.doc.bill_no, onchange: () => this.header("bill_no")},
						{fieldtype: "Column Break"},
						{fieldname: "bill_date", fieldtype: "Date", label: __("Supplier Invoice Date"),
							default: frm.doc.bill_date, onchange: () => this.header("bill_date")},
						{fieldtype: "Column Break"},
						{fieldname: "find", fieldtype: "Data", label: __("Find in Invoice"), onchange: () => this.filter()},
						{fieldtype: "Section Break"},
					] : []),
					{fieldname: "scan_feedback", fieldtype: "HTML"},
					{fieldname: "scan", fieldtype: "Data", options: "Barcode", label: __("Scan Barcode"),
						description: __("Scan, or enter a barcode and press Enter / Tab."), onchange: () => this.scan()},
					{fieldtype: "Column Break"},
					{fieldname: "item", fieldtype: "Link", options: "Item", label: __("Search Item"),
						get_query: () => ({filters: {disabled: 0, is_purchase_item: 1, has_variants: 0}})},
					{fieldtype: "Column Break"},
					{fieldname: "add", fieldtype: "Button", label: __("Add Item"), click: () => {
						const code = this.dialog.get_value("item");
						if (code) this.enqueue(() => this.add(this.packingChoice?.item_code === code ? this.packingChoice : {item_code: code}));
					}},
					...(!this.isInvoice ? [
						{fieldtype: "Column Break"},
						{fieldname: "find", fieldtype: "Data", label: __("Find in Receipt"), onchange: () => this.filter()},
					] : []),
					{fieldtype: "Section Break"},
					{fieldname: "keyboard_help", fieldtype: "HTML", options: `<div class="text-muted small">${esc(shortcutHelp())}</div>`},
					{fieldname: "items_html", fieldtype: "HTML"},
					{fieldname: "totals", fieldtype: "HTML"},
					{fieldname: "status", fieldtype: "HTML"},
				],
				primary_action_label: __("Save"), primary_action: () => this.save(false),
				secondary_action_label: __("Submit + New"), secondary_action: () => this.save(true),
			});
			const modal = this.dialog.$wrapper[0];
			const ownsKeyboard = () => editable(this.frm) && frappe.ui.open_dialogs?.slice(-1)[0] === this.dialog;
			// FieldGroup's text-input keypress handler otherwise invokes Save.
			modal.addEventListener("keypress", event => {
				if ((event.key === "Enter" || event.which === 13) && ownsKeyboard() && event.target.matches("input, select")) {
					event.preventDefault();
					event.stopImmediatePropagation();
				}
			}, true);
			modal.addEventListener("keydown", event => {
				if (!ownsKeyboard() || event.ctrlKey || event.altKey || event.metaKey || event.isComposing ||
					!event.target.matches("input, textarea, select")) return;
				if (event.key === "Tab" || (event.key === "Enter" && event.shiftKey)) {
					event.preventDefault();
					event.stopImmediatePropagation();
					for (const field of Object.values(this.dialog.fields_dict)) field.awesomplete?.close();
					this.dialog.get_field("scan").set_focus();
					return;
				}
				if (event.key !== "Enter" || event.target.closest("tbody tr") || event.target.tagName === "TEXTAREA") return;
				const search = this.dialog.get_field("item"), scan = this.dialog.get_field("scan");
				if ([search.$input[0], scan.$input[0]].includes(event.target)) return;
				const control = Object.values(this.dialog.fields_dict).find(field => field.$input?.[0] === event.target);
				if (control?.awesomplete?.opened) return;
				event.preventDefault();
				event.stopImmediatePropagation();
				if (event.repeat) return;
				const fields = Array.from(modal.querySelectorAll("input, select")).filter(input =>
					!input.disabled && !input.readOnly && !["hidden", "button", "submit"].includes(input.type) &&
					input.tabIndex !== -1 && input.getClientRects().length);
				const next = fields[fields.indexOf(event.target) + 1];
				if (next) next.focus();
			}, true);
			this.dialog.$wrapper.find(".modal-dialog").css({width: "96vw", maxWidth: "1600px"});
			bindItemRowEnter(this.dialog.get_field("items_html").$wrapper[0], "tbody tr", () =>
				editable(this.frm) && frappe.ui.open_dialogs?.slice(-1)[0] === this.dialog,
				() => this.dialog.get_field("item").set_focus(),
				() => this.dialog.get_field("scan").set_focus());
			const itemInput = this.dialog.get_field("item").$wrapper.find(".control-input");
			itemInput.css({display: "flex", alignItems: "center", gap: "8px"});
			itemInput.children().css({flex: "1 1 auto", minWidth: 0});
			const add = this.dialog.get_field("add");
			add.$wrapper.closest(".form-column").hide();
			add.$input.css({flex: "0 0 auto", margin: 0, border: "2px solid var(--border-color)"}).appendTo(itemInput);
			bindSupplierTab(this.dialog.get_field("supplier"), () => this.supplierFromTab());
			const search = this.dialog.get_field("item");
			search.$input[0].addEventListener("keydown", event => {
				if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey || event.isComposing) return;
				if (!["Enter", "Tab"].includes(event.key)) return;
				event.preventDefault();
				event.stopImmediatePropagation();
				if (event.repeat) return;
				if (event.key === "Tab") {
					search.awesomplete?.close();
					this.dialog.get_field("scan").set_focus();
				} else if (search.awesomplete?.opened && search.awesomplete.selected) {
					this.addSelectedPacking = true;
					search.awesomplete.select(undefined, undefined, event);
					Promise.resolve().then(() => { this.addSelectedPacking = false; });
				} else {
					this.dialog.get_field("add").$input.trigger("click");
				}
			}, true);
			window.retail?.purchase_packing_search?.bind(this.dialog.get_field("item"), choice => {
				this.packingChoice = choice;
				if (this.addSelectedPacking) {
					this.addSelectedPacking = false;
					this.enqueue(() => this.add(choice));
				}
			});
			// FieldGroup binds Enter to Save on text inputs. This field must scan instead.
			this.dialog.get_field("scan").$input.off("keypress").on("keydown.quickReceipt", event => {
				if (!["Enter", "Tab"].includes(event.key)) return;
				if (event.key === "Enter") {
					event.preventDefault();
					event.stopImmediatePropagation();
				}
				this.scan();
			});
			this.dialog.$wrapper.on("keydown.quickReceipt", event => {
				const key = shortcutKey(event);
				if (!key || !editable(this.frm) || frappe.ui.open_dialogs?.slice(-1)[0] !== this.dialog) return;
				event.preventDefault();
				event.stopImmediatePropagation();
				if (key === "a") {
					if (this.dialog.get_value("item")) this.dialog.get_field("add").$input.trigger("click");
					else this.dialog.get_field("item").set_focus();
				} else if (key !== "q") {
					this.dialog.get_field({b: "scan", i: "item", s: "supplier", w: "set_warehouse"}[key]).set_focus();
				}
			});
		}

		async supplierFromTab() {
			if (this.creatingSupplier) return;
			this.creatingSupplier = true;
			const field = this.dialog.get_field("supplier");
			const typed = String(field.$input.val() || "").trim();
			try {
				field.awesomplete?.close();
				// Keep an uncreated name out of the Link field's blur validation.
				field.set_input(this.frm.doc.supplier || "");
				// Use Supplier's standard quick-entry fields, validation and permissions.
				await frappe.ui.form.make_quick_entry("Supplier", async doc => {
					await this.dialog.set_value("supplier", doc.name);
					await this.queue;
					this.dialog.get_field("set_warehouse").set_focus();
				}, dialog => {
					this.supplierPopupOpen = true;
					if (typed && typed !== this.frm.doc.supplier) dialog.set_value("supplier_name", typed);
					const onhide = dialog.onhide;
					dialog.onhide = () => {
						onhide?.();
						this.supplierPopupOpen = false;
						this.creatingSupplier = false;
					};
				}, undefined, true);
			} finally {
				// The popup owns the guard until it closes.
				if (!this.supplierPopupOpen) this.creatingSupplier = false;
			}
		}

		useFastFill() {
			// The test harness has no visible dialog. Live Quick Entry does, and that
			// is the path which used to wait on a chain of item, price and tax calls.
			return Boolean(window.retail?.purchaseLine && this.lookups && this.dialog?.$wrapper?.is?.(":visible")
				&& !this.frm.doc.is_internal_supplier && !this.frm.doc.is_return
				&& Number(this.frm.doc.docstatus || 0) === 0);
		}

		noteItem(result) {
			const item = result?.item;
			if (!item?.name) return;
			this.items.set(item.name, item);
			const tracking = this.frm.__retail_purchase_tracking ||= {items: new Map(), generation: 0};
			tracking.items.set(item.name, item);
		}

		async present(row, scan = {}) {
			const frm = this.frm;
			this.scheduleSync(scan.serial_no ? 3200 : 1000);
			frm.refresh_field("items");
			this.render();
			await this.dialog.set_value("item", "");
			await this.dialog.set_value("find", "");
			this.packingChoice = null;
			await new Promise(resolve => frappe.after_ajax(resolve));
			const element = this.rows.get(row.name)?.element;
			element?.addClass("table-success");
			element?.[0].scrollIntoView({block: "nearest"});
			// Searching by name can land on the quantity so it can be edited.
			// A scan must stay in the barcode box: the next wedge would otherwise
			// type the barcode into Accepted Qty, then Enter into FOC Qty.
			if (scan.keepScan) this.focusScan();
			else focusFirstEditable(element?.[0]);
		}

		focusScan() {
			const field = this.dialog?.get_field("scan");
			field?.set_focus?.();
			setTimeout(() => field?.set_focus?.(), 0);
		}

		scan() {
			if (!this.dialog || this.saving || this.submitting) return;
			const field = this.dialog.get_field("scan");
			// Read the actual input: scanners can send Enter before the change event.
			const barcode = String(field.$input.val() || "").trim();
			if (!barcode) return;
			this.dialog.get_field("scan_feedback").$wrapper.empty();
			// Clear synchronously so Enter followed by change cannot scan twice.
			field.set_input("");
			this.focusScan();
			return this.enqueue(async () => {
				if (!this.required()) {
					if (!field.$input.val()) field.set_input(barcode);
					return;
				}
				try {
					if (this.useFastFill()) {
						const result = await window.retail.purchaseLine.fill(this.frm, {search_value: barcode, barcode});
						if (!result?.row) {
							const text = __("Cannot find Item with barcode {0}", [barcode]);
							this.dialog.get_field("status").$wrapper.text(text);
							this.dialog.get_field("scan_feedback").$wrapper.html(
								`<div class="alert alert-warning" role="alert" aria-live="assertive" style="margin-bottom:8px">${esc(text)}</div>`);
							field.set_focus();
							return;
						}
						this.noteItem(result);
						result.row.custom_item_barcode = this.barcode(result.row);
						await this.present(result.row, {barcode, serial_no: result.row.serial_no, keepScan: true});
						this.dialog.get_field("status").$wrapper.text(__("Added barcode: {0}", [barcode]));
						this.focusScan();
						return;
					}
					const {message} = await frappe.call({method: "retail.domains.item.packing_scan.scan_barcode", args: {search_value: barcode}});
					if (!message?.item_code) {
						const text = __("Cannot find Item with barcode {0}", [barcode]);
						this.dialog.get_field("status").$wrapper.text(text);
						this.dialog.get_field("scan_feedback").$wrapper.html(
							`<div class="alert alert-warning" role="alert" aria-live="assertive" style="margin-bottom:8px">${esc(text)}</div>`);
						field.set_focus();
						return;
					}
					if (message.scale_barcode_type) {
						frappe.throw(__("Use the full {0} for this scale barcode.", [this.frm.doc.doctype]));
					}
					await this.add(Object.assign({}, message, {keepScan: true}));
					this.dialog.get_field("status").$wrapper.text(__("Added barcode: {0}", [barcode]));
					this.focusScan();
				} catch (error) {
					if (!field.$input.val()) field.set_input(barcode);
					throw error;
				}
			});
		}

		enqueue(action) {
			this.pending++;
			this.queue = this.queue.then(() => {
				// Reuse read-only lookups within one action, then fetch fresh values on the next edit.
				this.lookups = new Map();
				return action();
			}).catch(error => {
				console.error(error);
				this.dialog.get_field("status").$wrapper.text(__("Could not apply the last action. Check the message and correct the entry before saving."));
				this.failed = true;
			}).finally(() => { this.pending--; });
			return this.queue;
		}

		lookup(request) {
			if (!this.lookups || this.frm.__quick_receipt !== this || !this.dialog.$wrapper.is(":visible")) {
				return frappe.call(request);
			}
			const cache = this.lookups;
			const key = this.lookupKey(request);
			if (!cache.has(key)) {
				const pending = Promise.resolve(frappe.call(request)).catch(error => {
					cache.delete(key);
					throw error;
				});
				cache.set(key, pending);
			}
			return cache.get(key);
		}

		lookupKey(request) {
			// JSON omits undefined; the equivalent HTTP null optional arguments must
			// use the same key when results arrive from the bundled server read.
			const args = request.args || {};
			return JSON.stringify([request.method, Object.keys(args).sort()
				.filter(key => args[key] != null).map(key => [key, args[key]])]);
		}

		async readItem(scan) {
			if (this.items.has(scan.item_code)) return this.items.get(scan.item_code);
			if (!this.lookups || this.frm.__quick_receipt !== this || !this.dialog.$wrapper.is(":visible")) {
				return frappe.db.get_doc("Item", scan.item_code);
			}
			this.dialog.get_field("status").$wrapper.text(__("Adding item…"));
			const empty = (this.frm.doc.items || []).find(row => !row.item_code);
			const {message} = await this.lookup({
				method: "retail.domains.purchase.quick_entry.item_data",
				args: {item_code: scan.item_code, parent_doctype: this.frm.doc.doctype,
					uom: scan.uom, transaction_type: this.frm.doc.transaction_type,
					item_tax_template: empty?.item_tax_template},
			});
			if (message?.item?.name !== scan.item_code) frappe.throw(__("Could not load the selected Item."));
			for (const result of message.lookups || []) {
				const key = this.lookupKey(result);
				if (!this.lookups.has(key)) this.lookups.set(key, Promise.resolve({message: result.message}));
			}
			frappe.model.sync(message.item);
			return message.item;
		}

		async prepareItem(row, itemCode) {
			// These reads do not depend on one another. Finish them before native field
			// handlers run serially, so a remote connection pays for one round trip.
			const purchaseVat = this.lookup({method: "retail.domains.transactions.vat.get_transaction_item_vat_rate", args: {
				item_code: itemCode, child_doctype: row.doctype, parent_doctype: this.frm.doc.doctype,
				transaction_type: this.frm.doc.transaction_type, item_tax_template: row.item_tax_template,
			}});
			const selling = frappe.meta.has_field(row.doctype, "custom_cur_sell_rate") ? [
				this.lookup({method: "retail.domains.purchase.selling_price.get_standard_selling_rate", args: {item_code: itemCode, uom: row.uom}}),
				this.lookup({method: "retail.domains.purchase.selling_price.get_item_selling_vat_rate", args: {item_code: itemCode}}),
			] : [];
			await Promise.all([purchaseVat, ...selling]);
		}

		header(field) {
			if (!this.dialog) return;
			const value = this.dialog.get_value(field);
			if (value === this.frm.doc[field]) return;
			this.enqueue(async () => {
				if (field === "posting_date") await this.frm.set_value("set_posting_time", 1);
				await this.frm.set_value(field, value);
				if (field === "update_stock") {
					this.dialog.set_df_property("set_warehouse", "reqd", Boolean(Number(this.frm.doc.update_stock)));
				}
				this.scheduleSync();
				this.render();
			});
		}

		required() {
			if (this.frm.doc.supplier && (!this.stockEnabled() || this.frm.doc.set_warehouse)) return true;
			frappe.msgprint(__(this.stockEnabled() ? "Select Supplier and Warehouse first." : "Select Supplier first."));
			return false;
		}

		stockEnabled() {
			return !this.isInvoice || Boolean(Number(this.frm.doc.update_stock));
		}

		scheduleSync(delay = 1000) {
			// Let the next edit run while VAT/serial handlers finish in the background.
			this.settleAt = Math.max(this.settleAt || 0, Date.now() + delay);
			clearTimeout(this.syncTimer);
			this.syncTimer = setTimeout(async () => {
				try {
					await this.settle();
					if (this.frm.__quick_receipt === this) this.render();
				} catch (error) {
					console.error(error);
					this.failed = true;
					this.dialog.get_field("status").$wrapper.text(__("Could not refresh the entry. Check the message before saving."));
				}
			}, this.settleAt - Date.now());
		}

		async rowReady(row) {
			// Inclusive-price handlers ignore edits while an earlier VAT write is active.
			// Await that work, without holding up every edit for a fixed quiet period.
			while (row.__retail_vat_syncing || row.__retail_sell_price_syncing) {
				await new Promise(resolve => setTimeout(resolve, 16));
			}
		}

		async setRowValue(row, field, value) {
			await this.rowReady(row);
			await frappe.model.set_value(row.doctype, row.name, field, value);
			if (field === "uom") {
				// The core UOM handler can start callback-based price requests without
				// returning their promise. Cached Retail reads must not let the next
				// field overtake those native callbacks and temporarily zero the rate.
				await new Promise(resolve => frappe.after_ajax(resolve));
			}
			await this.rowReady(row);
		}

		async settle() {
			// Save waits for the remaining debounce time, once for the whole queue.
			while (this.settleAt > Date.now()) {
				await new Promise(resolve => setTimeout(resolve, this.settleAt - Date.now()));
			}
			await new Promise(resolve => frappe.after_ajax(resolve));
			for (const row of this.frm.doc.items || []) await this.rowReady(row);
			await window.retail?.transaction_items?.flushVatTaxRows?.(this.frm);
		}

		async add(scan) {
			if (!this.required()) return;
			if (this.useFastFill()) {
				const result = await window.retail.purchaseLine.fill(this.frm, scan);
				if (!result?.row) frappe.throw(__("Could not load the selected Item."));
				this.noteItem(result);
				result.row.custom_item_barcode = this.barcode(result.row);
				await this.present(result.row, scan);
				return;
			}
			const frm = this.frm;
			const master = await this.readItem(scan);
			this.items.set(scan.item_code, master);
			// The tracking handler needs only flags from this already-authorized Item read.
			frm.__retail_purchase_tracking?.items.set(scan.item_code, master);
			if (scan.serial_no && (frm.doc.items || []).some(row => row.item_code === scan.item_code &&
				String(row.serial_no || "").split(/\s*\n\s*/).includes(scan.serial_no))) {
				frappe.throw(__("This serial number is already in the receipt."));
			}
			const uom = scan.uom || master.purchase_uom || master.stock_uom;
			const matches = (frm.doc.items || []).filter(row => row.item_code === scan.item_code && row.uom === uom &&
				!row.custom_foc_parent && !row.serial_and_batch_bundle && !row.rejected_qty && (row.warehouse || "") === (frm.doc.set_warehouse || "") &&
				(!scan.batch_no || !row.batch_no || row.batch_no === scan.batch_no));
			// Do not merge distinct PO lines or rows with different negotiated rates.
			let row = matches.length === 1 ? matches[0] : null;
			if (row) {
				await this.setRowValue(row, "qty", flt(row.qty) + 1);
			} else {
				row = (frm.doc.items || []).find(row => !row.item_code) || frm.add_child("items");
				if (master.has_serial_no || master.has_batch_no) row.use_serial_batch_fields = 1;
				// Native barcode entry preserves the supplied UOM when loading item
				// details. Seed the same inputs on the empty row so packing scans do
				// not load stock-UOM pricing first and then price the packing again.
				const barcode = scan.barcode || this.barcode({item_code: scan.item_code, uom});
				const initializePacking = barcode && !frm.doc.is_internal_supplier;
				if (initializePacking) {
					row.barcode = barcode;
					row.uom = uom;
				}
				if (this.lookups && this.dialog.$wrapper.is(":visible")) await this.prepareItem(row, scan.item_code);
				await this.setRowValue(row, "item_code", scan.item_code);
				await this.setRowValue(row, "uom", uom);
				if (initializePacking) {
					// Core's item callback starts this calculation without returning
					// its promise. Await the native calculation before displaying the
					// initialized packing, including its negotiated price/discounts.
					await frm.script_manager.trigger("price_list_rate", row.doctype, row.name);
					await this.rowReady(row);
				}
				await this.setRowValue(row, {qty: 1, warehouse: frm.doc.set_warehouse});
			}
			// Keep the scan identity without invoking the native barcode handler (which resets qty).
			if (scan.barcode) row.barcode = scan.barcode;
			row.custom_item_barcode = this.barcode(row);
			if (scan.batch_no) await this.setRowValue(row, "batch_no", scan.batch_no);
			if (scan.serial_no) {
				const serials = [...new Set(`${row.serial_no || ""}\n${scan.serial_no}`.split(/\s*\n\s*/).filter(Boolean))];
				await this.setRowValue(row, "serial_no", serials.join("\n"));
			}
			this.scheduleSync(scan.serial_no ? 3200 : 1000);
			frm.refresh_field("items");
			this.render();
			await this.dialog.set_value("item", "");
			await this.dialog.set_value("find", "");
			this.packingChoice = null;
			// Link validation and native item callbacks can restore search focus.
			// Apply the table focus only after those callbacks have completed.
			await new Promise(resolve => frappe.after_ajax(resolve));
			const element = this.rows.get(row.name)?.element;
			element?.addClass("table-success");
			element?.[0].scrollIntoView({block: "nearest"});
			if (scan.keepScan) this.focusScan();
			else focusFirstEditable(element?.[0]);
		}

		async loadItems() {
			const codes = [...new Set((this.frm.doc.items || []).map(row => row.item_code).filter(code => code && !this.items.has(code)))];
			if (!codes.length) return;
			const masters = await frappe.db.get_list("Item", {fields: ["name", "has_serial_no", "has_batch_no", "custom_barcode", "stock_uom", "purchase_uom"], filters: {name: ["in", codes]}, limit: codes.length});
			for (const master of masters) this.items.set(master.name, master);
			// Existing packing rows may only have the master barcode in the display field.
			await Promise.all(masters.filter(master => (this.frm.doc.items || []).some(row =>
				row.item_code === master.name && !row.barcode && row.uom && row.uom !== master.stock_uom))
				.map(async master => this.items.set(master.name, await frappe.db.get_doc("Item", master.name))));
			return masters.length;
		}

		barcode(row) {
			if (row.barcode) return row.barcode;
			const master = this.items.get(row.item_code) || {};
			if (row.uom && row.uom !== master.stock_uom) {
				const packings = (master.custom_retail_packing_detail || []).filter(packing =>
					packing.uom === row.uom && (!row.conversion_factor || flt(packing.conversion_factor) === flt(row.conversion_factor)));
				const barcodes = [...packings, ...(master.barcodes || []).filter(barcode => barcode.uom === row.uom)]
					.map(packing => packing.barcode).filter(Boolean);
				return barcodes.includes(row.custom_item_barcode) ? row.custom_item_barcode : barcodes[0] || "";
			}
			return row.custom_item_barcode || master.custom_barcode || "";
		}

		async removeRows(rows) {
			const frm = this.frm;
			if (!editable(frm)) return;
			const names = new Set(rows.filter(row => !row.custom_foc_parent).map(row => row.name));
			const keys = new Set((frm.doc.items || []).filter(row => names.has(row.name) && row.custom_foc_key).map(row => row.custom_foc_key));
			const removed = (frm.doc.items || []).filter(item => names.has(item.name) || keys.has(item.custom_foc_parent));
			if (!removed.length) return;
			// Run native removal hooks before changing any paid or generated free row.
			for (const item of removed) await frm.script_manager.trigger("before_items_remove", item.doctype, item.name);
			for (const item of removed) {
				frappe.model.clear_doc(item.doctype, item.name);
				await frm.script_manager.trigger("items_remove", item.doctype, item.name);
				this.selectedRows.delete(item.name);
			}
			frm.dirty();
			frm.refresh_field("items");
			await frm.script_manager.trigger("calculate_taxes_and_totals");
			this.scheduleSync();
			this.render();
		}

		render() {
			const target = this.dialog.get_field("items_html").$wrapper;
			const previousRows = this.rows;
			// Build completely before replacing the visible table.
			const wrapper = $("<div></div>");
			try {
			const masterFor = row => {
				if (!this.stockEnabled() || (this.isInvoice && Number(row.is_fixed_asset))) return {};
				return this.items.get(row.item_code) || this.frm.__retail_purchase_tracking?.items.get(row.item_code) || {};
			};
			const serial = (this.frm.doc.items || []).some(row => masterFor(row).has_serial_no);
			const batch = (this.frm.doc.items || []).some(row => masterFor(row).has_batch_no);
			const layout = JSON.stringify([serial, batch]);
			const reuse = this.layout === layout;
			wrapper.html(`<div style="max-height:45vh;overflow:auto"><table class="table table-bordered" style="min-width:1050px;margin:0">
				<thead style="position:sticky;top:0;background:var(--fg-color);z-index:2"><tr><th style="width:36px"><input type="checkbox" class="quick-receipt-select-all" aria-label="${esc(__("Select all visible rows"))}"></th>${["Item Name", "Barcode", "UOM", ...(serial ? ["Serial No"] : []), ...(batch ? ["Batch No"] : []), this.isInvoice ? "Qty" : "Accepted Qty", "FOC Qty", "Rate Including VAT", "Rate Excluding VAT", "Amount Including VAT", "Amount Excluding VAT", "VAT Amount"].map(label => `<th>${__(label)}</th>`).join("")}</tr></thead><tbody></tbody></table></div>
				<div class="quick-receipt-selection hidden" role="toolbar" aria-label="${esc(__("Selected rows"))}" style="position:sticky;bottom:12px;z-index:3;width:max-content;margin:12px auto 0;padding:8px 12px;border-radius:var(--border-radius-md);background:var(--fg-color);box-shadow:var(--shadow-md)">
					<span class="quick-receipt-selection-count" aria-live="polite" style="margin-right:12px"></span><button type="button" class="btn btn-sm btn-danger quick-receipt-delete">${__("Delete")}</button>
				</div>`);
			this.rows = new Map();
			for (const row of this.frm.doc.items || []) {
				if (!row.item_code || (row.custom_foc_parent && !masterFor(row).has_serial_no && !masterFor(row).has_batch_no)) continue;
				const rowLayout = JSON.stringify([row.item_code, row.item_name, this.barcode(row),
					masterFor(row).has_serial_no, masterFor(row).has_batch_no, Boolean(row.custom_foc_parent), Boolean(row.serial_and_batch_bundle)]);
				const previous = reuse && previousRows?.get(row.name);
				if (previous?.row === row && previous.layout === rowLayout) {
					this.rows.set(row.name, previous);
					continue;
				}
				const element = $(`<tr><td class="quick-receipt-select-cell"></td><td style="min-width:230px"><strong>${esc(row.item_name || row.item_code)}${row.custom_foc_parent ? " (FOC)" : ""}</strong><div class="small text-muted">${esc(row.item_code)}</div></td></tr>`).appendTo(wrapper.find("tbody"));
				let selection;
				if (!row.custom_foc_parent) {
					selection = $('<input type="checkbox" class="quick-receipt-select">').attr("aria-label", __("Select {0}", [row.item_name || row.item_code]))
						.prop("checked", this.selectedRows.has(row.name)).appendTo(element.find(".quick-receipt-select-cell"))
						.on("change", () => {
							if (selection.prop("checked")) this.selectedRows.add(row.name);
							else this.selectedRows.delete(row.name);
							this.updateSelection();
						});
				}
				$(`<td>${esc(this.barcode(row))}</td>`).appendTo(element);
				const controls = {};
				for (const [fieldname, fieldtype, label] of [
					["uom", "Link", "UOM"],
					...(serial ? [["serial_no", "Small Text", "Serial No"]] : []),
					...(batch ? [["batch_no", "Link", "Batch No"]] : []),
					["qty", "Float", this.isInvoice ? "Qty" : "Accepted Qty"], ["custom_foc_qty", "Float", "FOC Qty"],
					["custom_rate_including_vat", "Currency", "Rate Including VAT"], ["rate", "Currency", "Rate Excluding VAT"],
					["custom_amount_including_vat", "Currency", "Amount Including VAT"], ["amount", "Currency", "Amount Excluding VAT"],
					["custom_vat_amount", "Currency", "VAT Amount"],
				]) {
					const cell = $('<td style="min-width:140px"></td>').appendTo(element);
					if ((fieldname === "serial_no" && !masterFor(row).has_serial_no) || (fieldname === "batch_no" && !masterFor(row).has_batch_no)) continue;
					const control = frappe.ui.form.make_control({parent: cell, render_input: true, only_input: true, df: {
						fieldname, fieldtype, label: __(label), options: fieldtype === "Link" ? (fieldname === "batch_no" ? "Batch" : "UOM") : undefined,
						read_only: ["serial_no", "batch_no"].includes(fieldname) ? Boolean(row.serial_and_batch_bundle) :
							["uom", "custom_vat_amount"].includes(fieldname) || Boolean(row.custom_foc_parent),
						get_query: () => fieldname === "batch_no" ? {filters: {item: row.item_code, disabled: 0}} : ({query: "erpnext.controllers.queries.get_item_uom_query", filters: {item_code: row.item_code}}),
						get_route_options_for_new_doc: () => ({item: row.item_code}),
						onchange: () => {
							if (this.syncing || control.df.read_only) return;
							const value = control.get_value();
							if (value == row[fieldname]) return;
							this.enqueue(async () => {
								if (["Currency", "Float"].includes(fieldtype) && flt(value) < 0) {
									control.set_value(row[fieldname]);
									frappe.throw(__("Quantities and rates cannot be negative."));
								}
								if (["serial_no", "batch_no"].includes(fieldname)) row.use_serial_batch_fields = 1;
								await this.setRowValue(row, fieldname, value);
								// ERPNext updates quantity from serial numbers after 3 seconds.
								this.scheduleSync(fieldname === "serial_no" ? 3200 : 1000);
								this.sync();
							});
						},
					}});
					control.$wrapper.find(".control-label, .help-box").hide();
					control.$wrapper.css("margin-bottom", 0);
					controls[fieldname] = control;
					if (fieldname === "serial_no" && control.$input) {
						control.$input.attr("rows", 1).css({minHeight: "32px", height: "32px", overflowY: "hidden", resize: "none"})
							.on("input.quickReceipt", () => resizeSerial(control));
						const setInput = control.set_input;
						control.set_input = function (...args) {
							const result = setInput.apply(this, args);
							resizeSerial(this);
							return result;
						};
					}
					if (["serial_no", "batch_no"].includes(fieldname)) {
						window.retail?.purchase_tracking?.bindCreate(this.frm, row, fieldname, control);
					}
					if (["uom", "batch_no"].includes(fieldname)) {
						control.$input?.on("awesomplete-open.quickReceipt", () => {
							const rect = control.$input[0].getBoundingClientRect();
							// Fixed positioning escapes the receipt table's scroll clipping.
							const dropdown = control.awesomplete.ul;
							$(dropdown).css("position", "fixed");
							// Bootstrap's transformed modal can be the fixed-position containing block.
							const bounds = dropdown.offsetParent?.getBoundingClientRect();
							$(dropdown).css({top: "auto",
								bottom: `${(bounds?.bottom ?? window.innerHeight) - rect.top + 4}px`,
								left: `${rect.left - (bounds?.left || 0)}px`, right: "auto",
								width: `${Math.max(rect.width, 180)}px`, maxHeight: `${Math.max(60, Math.min(240, rect.top - 16))}px`,
								overflowY: "auto", margin: 0, zIndex: 1060});
						});
					}
				}
				this.rows.set(row.name, {element, controls, row, selection, layout: rowLayout});
			}
			wrapper.find(".quick-receipt-select-all").on("change", event => {
				for (const {element, row, selection} of this.rows.values()) {
					if (!selection || !element.is(":visible")) continue;
					if (event.target.checked) this.selectedRows.add(row.name);
					else this.selectedRows.delete(row.name);
				}
				this.updateSelection();
			});
			wrapper.find(".quick-receipt-delete").on("click", () => {
				if (this.removingRows || this.saving || this.submitting) return;
				const rows = (this.frm.doc.items || []).filter(row => this.selectedRows.has(row.name));
				this.removingRows = true;
				this.updateSelection();
				this.enqueue(async () => {
					try { await this.removeRows(rows); }
					finally { this.removingRows = false; this.updateSelection(); }
				});
			});
			wrapper.find("div[style*='overflow:auto']").on("scroll.quickReceipt", () => {
				for (const {controls} of this.rows.values()) {
					controls.uom.awesomplete?.close();
					controls.batch_no?.awesomplete?.close();
				}
			});
			this.sync();
			if (reuse) {
				// Keep existing controls, focus and scroll position when rows are added/removed.
				for (const [name, previous] of previousRows) {
					if (this.rows.get(name) !== previous) previous.element.remove();
				}
				const body = target.find("tbody");
				let index = 0;
				for (const {element} of this.rows.values()) {
					const current = body.children().eq(index++);
					if (current[0] === element[0]) continue;
					if (current.length) element.insertBefore(current);
					else element.appendTo(body);
				}
			} else {
				target.empty().append(wrapper.contents());
			}
			this.layout = layout;
			this.filter();
			} catch (error) {
				this.rows = previousRows;
				throw error;
			}
		}

		updateSelection() {
			const visible = [];
			for (const name of this.selectedRows) {
				if (!this.rows.has(name)) this.selectedRows.delete(name);
			}
			for (const {element, row, selection} of this.rows.values()) {
				if (!selection) continue;
				selection.prop("checked", this.selectedRows.has(row.name)).prop("disabled", Boolean(this.removingRows));
				if (element.is(":visible")) visible.push(row.name);
			}
			const wrapper = this.dialog.get_field("items_html").$wrapper;
			const count = visible.filter(name => this.selectedRows.has(name)).length;
			wrapper.find(".quick-receipt-select-all").prop("checked", visible.length > 0 && count === visible.length)
				.prop("indeterminate", count > 0 && count < visible.length).prop("disabled", !visible.length || Boolean(this.removingRows));
			wrapper.find(".quick-receipt-selection").toggleClass("hidden", !this.selectedRows.size);
			wrapper.find(".quick-receipt-selection-count").text(__("{0} selected", [this.selectedRows.size]));
			wrapper.find(".quick-receipt-delete").prop("disabled", Boolean(this.removingRows));
		}

		sync() {
			this.syncing = true;
			try {
				for (const {controls, row} of this.rows.values()) {
					for (const [field, control] of Object.entries(controls)) {
						// Do not replace a value the user is still typing.
						if (control.$input) {
							if (!control.$input.is(":focus") && control.get_value() != (row[field] ?? "")) control.set_input(row[field] ?? "");
						} else {
							control.value = row[field] ?? "";
							control.refresh();
						}
					}
				}
			} finally { this.syncing = false; }
			const doc = this.frm.doc;
			const qty = (doc.items || []).filter(row => !row.custom_foc_parent).reduce((sum, row) => sum + flt(row.qty) + flt(row.custom_foc_qty), 0);
			const totals = this.dialog.get_field("totals").$wrapper;
			if (!totals.find(".quick-receipt-totals").length) {
				const summary = $('<div class="quick-receipt-totals" role="group"></div>')
					.attr("aria-label", __("Totals"))
					.css({display: "flex", alignItems: "center", flexWrap: "nowrap", gap: "16px", marginTop: "12px",
						padding: "8px 0", fontSize: "14px", lineHeight: "1.6", whiteSpace: "nowrap", overflowX: "auto"});
				for (const [key, label] of [["qty", "Total Qty (including FOC)"], ["net", "Net"], ["tax", "VAT / Charges"], ["grand", "Grand Total"]]) {
					if (key !== "qty") $('<span aria-hidden="true">|</span>').css({color: "var(--border-color)", fontWeight: 400}).appendTo(summary);
					const group = $('<span></span>').css({display: "inline-flex", alignItems: "baseline", gap: "6px", flexShrink: 0});
					$('<span class="text-muted"></span>').text(__(label) + ":").css("font-weight", 400).appendTo(group);
					$('<span></span>').attr("data-total", key).css({fontWeight: key === "grand" ? 700 : 600,
						color: "var(--text-color)", fontVariantNumeric: "tabular-nums"}).appendTo(group);
					group.appendTo(summary);
				}
				totals.empty().append(summary);
			}
			for (const [key, value] of Object.entries({qty, net: format_currency(doc.net_total, doc.currency),
				tax: format_currency(doc.total_taxes_and_charges, doc.currency), grand: format_currency(doc.grand_total, doc.currency)})) {
				totals.find(`[data-total="${key}"]`).text(value);
			}
		}

		filter() {
			const term = (this.dialog.get_value("find") || "").toLowerCase();
			for (const {element, row, controls} of this.rows?.values() || []) {
				element.toggle(`${row.item_code} ${row.item_name}`.toLowerCase().includes(term));
				resizeSerial(controls.serial_no);
			}
			this.updateSelection();
		}

		async save(submit) {
			if (this.saving || this.submitting) return;
			this.saving = true;
			try {
				const focused = this.dialog.$wrapper.find("input:focus, textarea:focus, select:focus")[0];
				const controls = [...Object.values(this.dialog.fields_dict),
					...[...this.rows.values()].flatMap(({controls}) => Object.values(controls))];
				const active = controls.find(control => control.$input?.[0] === focused);
				if (active?.parse_validate_and_set_in_model && active.df.fieldname !== "scan") {
					while (active.inside_change_event) await new Promise(resolve => setTimeout(resolve, 16));
					await active.parse_validate_and_set_in_model(active.get_input_value());
				}
				this.dialog.$wrapper.find("input:focus, textarea:focus, select:focus").trigger("change").trigger("blur");
				this.dialog.$wrapper.find(".modal-body").css("pointer-events", "none");
				this.dialog.$wrapper.find(".modal-footer button").prop("disabled", true);
				await this.settle();
				await this.queue;
				if (this.failed) {
					this.failed = false;
					frappe.msgprint(__("Review the last failed entry, then press Save again."));
					return;
				}
				if (!this.required()) return;
				if (!(this.frm.doc.items || []).some(row => row.item_code && !row.custom_foc_parent)) {
					frappe.msgprint(__("Add at least one item."));
					return;
				}
				await this.settle();
				if (this.frm.is_dirty() || this.frm.is_new()) await this.frm.save("Save", null, null, () => {});
				if (this.frm.doc.docstatus !== 0 || this.frm.is_dirty()) return;
				// Saving a new document changes its route and can close the modal.
				this.dialog.show();
				this.render();
				this.dialog.get_field("status").$wrapper.text(__("Saved draft: {0}", [this.frm.doc.name]));
				if (submit) {
					this.submitting = true;
					this.frm.__quick_receipt_next = {
						company: this.frm.doc.company, set_warehouse: this.frm.doc.set_warehouse,
						custom_allow_selling_price: this.frm.doc.custom_allow_selling_price,
						custom_update_item_master_rates: this.frm.doc.custom_update_item_master_rates,
						...(this.isInvoice ? {update_stock: this.frm.doc.update_stock} : {}),
					};
					this.frm.savesubmit(null, null, () => {
						delete this.frm.__quick_receipt_next;
						this.submitting = false;
					});
				}
			} catch (error) {
				this.submitting = false;
				delete this.frm.__quick_receipt_next;
				throw error;
			} finally {
				this.saving = false;
				this.dialog.$wrapper.find(".modal-body").css("pointer-events", "");
				this.dialog.$wrapper.find(".modal-footer button").prop("disabled", false);
			}
		}
	}
})();

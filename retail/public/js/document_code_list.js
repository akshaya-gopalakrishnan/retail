// Shared document-list behavior, kept in the Retail app rather than Frappe core.
(() => {
	frappe.provide("retail");
	function code_field(listview) {
		if (listview.meta.fields.some(df => df.fieldname === "custom_document_code")) {
			return "custom_document_code";
		}
		return listview.doctype === "Item" ? "item_code" : "name";
	}
	function code_label() {
		return __("ID");
	}

	function add_code_filter(listview) {
		const fieldname = code_field(listview);
		const label = code_label(listview);
		const fields = listview.page.fields_dict;
		if (fieldname === "custom_document_code" && fields.name) {
			const identity_label = listview.doctype === "User" ? __("Login") : __("Name");
			fields.name.df.label = identity_label;
			fields.name.$input?.attr("placeholder", identity_label);
		}
		const existing = fields[fieldname];
		const value = existing?.get_value() || "";
		const wrapper = listview.filter_area.standard_filters_wrapper;
		// Reuse the Sales Invoice autocomplete, including its existing query handler.
		if (existing?.df.fieldtype === "Autocomplete") {
			existing.df.label = label;
			existing.$input?.attr("placeholder", label);
			existing.$wrapper.find(".control-label").text(label);
			existing.$wrapper.prependTo(wrapper);
			return;
		}
		existing?.$wrapper.remove();
		delete fields[fieldname];
		const control = listview.page.add_field({
			fieldname,
			fieldtype: "Autocomplete",
			label,
			condition: "like",
			ignore_validation: true,
			onchange: () => listview.filter_area.debounced_refresh_list_view(),
		}, wrapper);
		control.set_input(value);
		control.$wrapper.prependTo(wrapper);
		let request = 0;
		const suggest = frappe.utils.debounce(async () => {
			const sequence = ++request;
			const term = control.$input.val() || "";
			const rows = await frappe.db.get_list(listview.doctype, {
				fields: [fieldname],
				filters: [[fieldname, "like", `%${term}%`]],
				order_by: `${fieldname} asc`,
				limit: 30,
			});
			if (sequence !== request || term !== control.$input.val()) return;
			control.set_data(rows.filter(row => row[fieldname]).map(row => ({
				value: row[fieldname],
				label: frappe.utils.escape_html(row[fieldname]),
			})));
			if (control.$input.is(":focus")) control.awesomplete.evaluate();
		}, 200);
		control.$input.on("input focus", suggest);
		listview.page.show_form();
	}

	function install_list_patch() {
		if (!frappe.views?.ListView) return;
		const prototype = frappe.views.ListView.prototype;
		if (prototype.retail_document_codes) return;
		prototype.retail_document_codes = true;
		const set_fields = prototype.set_fields;
		prototype.set_fields = async function () {
			const fieldname = code_field(this);
			this.settings.add_fields = [...new Set([...(this.settings.add_fields || []), fieldname])];
			return set_fields.call(this);
		};
		const refresh = prototype.refresh;
		prototype.refresh = async function (...args) {
			if (code_field(this) === "custom_document_code") {
				await frappe.call("retail.document_codes.ensure_codes", { doctype: this.doctype });
			}
			return refresh.apply(this, args);
		};
		const setup_columns = prototype.setup_columns;
		prototype.setup_columns = function () {
			setup_columns.call(this);
			const fieldname = code_field(this);
			// Keep the descriptive subject beside the short identifier.
			this.columns = this.columns.filter(column => {
				if (column.df?.fieldname === fieldname) return false;
				if (column.df?.fieldname === "name" && fieldname === "item_code") return false;
				if (column.df?.fieldname === "name" && fieldname === "custom_document_code") {
					if (this.doctype !== "User" && this.meta.title_field && this.meta.title_field !== "name") return false;
					column.df = { ...column.df, label: this.doctype === "User" ? __("Login") : __("Name") };
				}
				return true;
			});
			const subject = this.columns.find(column => column.type === "Subject");
			if (subject) subject.type = "Field";
			this.columns.unshift({
				type: "Subject",
				df: { fieldname, label: code_label(this), fieldtype: "Data" },
			});
		};
		const setup_view = prototype.setup_view;
		prototype.setup_view = function () {
			setup_view.call(this);
			add_code_filter(this);
		};
	}
	function install_form_patch() {
		if (!frappe.ui?.form?.Toolbar) return;
		const prototype = frappe.ui.form.Toolbar.prototype;
		if (prototype.retail_document_codes) return;
		prototype.retail_document_codes = true;
		const set_title = prototype.set_title;
		prototype.set_title = function () {
			set_title.call(this);
			const code = this.frm.doc?.custom_document_code;
			if (code && !this.frm.is_new()) {
				// Current Desk markup uses .sub-heading rather than the legacy h6.
				if (!this.page.$sub_title_area.length) {
					this.page.$sub_title_area = this.page.$title_area.find(".sub-heading");
				}
				this.page.set_title_sub(frappe.utils.escape_html(code));
				this.page.$sub_title_area.css("cursor", "copy").off("click").on("click.retail_code", event => {
					event.stopImmediatePropagation();
					frappe.utils.copy_to_clipboard(code);
				});
			}
		};
	}
	function install() {
		install_list_patch();
		install_form_patch();
	}
	// Desk loads list/form bundles before Retail. Support early execution without fetching them.
	install();
	if ((!frappe.views?.ListView || !frappe.ui?.form?.Toolbar) && !retail.document_codes_init_pending) {
		retail.document_codes_init_pending = true;
		$(function () {
			retail.document_codes_init_pending = false;
			install();
		});
	}
})();

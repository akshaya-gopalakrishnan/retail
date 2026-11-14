frappe.ui.form.on("POS Operator Privilege", {
	refresh(frm) {
		apply_privilege_grid(frm);
		add_privilege_buttons(frm);
		// Retail-app contains several workspaces; this is an employee setting.
		frappe.breadcrumbs.add({
			doctype: frm.doctype,
			module: "Retail-app",
			workspace: "Settings",
		});
		if (!frappe.is_mobile()) {
			frm.page.sidebar.removeClass("hide-sidebar").show();
		}
	},
});

function add_privilege_buttons(frm) {
	const wrapper = frm.fields_dict.disabled.$wrapper;
	wrapper.find(".pos-privilege-actions").remove();
	if (!frm.perm?.some((permission) => permission.write)) return;

	const actions = $('<span class="pos-privilege-actions"></span>')
		.css({ display: "inline-flex", gap: "8px", marginLeft: "16px" });
	for (const [label, value] of [[__("Select All"), 1], [__("Unselect All"), 0]]) {
		$('<button type="button" class="btn btn-default btn-xs"></button>')
			.text(label)
			.on("click", () => set_all_privileges(frm, value))
			.appendTo(actions);
	}
	wrapper.find(".checkbox > label").after(actions);
}

function apply_privilege_grid(frm) {
	// Each native form column is a category, with its own vertical checklist.
	document.getElementById("retail-pos-privilege-grid-style")?.remove();
	const style_id = "retail-pos-privilege-categories-style";
	frm.layout.sections_dict.privilege_categories_section?.wrapper.addClass("pos-privilege-categories");
	document.getElementById(style_id)?.remove();
	const style = document.createElement("style");
	style.id = style_id;
	style.textContent = `
		.form-section[data-fieldname="privilege_categories_section"] > .section-body {
			display: grid !important;
			grid-template-columns: repeat(5, minmax(0, 1fr));
			gap: 24px;
			align-items: start;
		}
		.form-section[data-fieldname="privilege_categories_section"] > .section-body > .form-column {
			display: block !important;
			width: auto !important;
			max-width: none !important;
			min-width: 0;
			padding: 0;
		}
		.form-section[data-fieldname="privilege_categories_section"] > .section-body > .form-column:first-child {
			padding-left: 20px;
		}
		.form-section[data-fieldname="privilege_categories_section"] .column-label {
			display: block;
			font-size: var(--text-base);
			font-weight: 600;
			min-height: 44px;
			margin-bottom: 16px;
		}
		.form-section[data-fieldname="privilege_categories_section"] .frappe-control[data-fieldtype="Check"] {
			margin-bottom: 12px;
		}
		@media (max-width: 991px) {
			.form-section[data-fieldname="privilege_categories_section"] > .section-body {
				grid-template-columns: repeat(2, minmax(0, 1fr));
			}
		}
		@media (max-width: 575px) {
			.form-section[data-fieldname="privilege_categories_section"] > .section-body {
				grid-template-columns: 1fr;
			}
		}
	`;
	document.head.appendChild(style);
}

function set_all_privileges(frm, value) {
	const values = {};
	for (const field of frm.meta.fields) {
		if (field.fieldtype === "Check" && field.fieldname !== "disabled"
			&& !field.read_only && !frm.fields_dict[field.fieldname]?.df.read_only) {
			values[field.fieldname] = value;
		}
	}
	return frm.set_value(values);
}

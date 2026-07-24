(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Sales Invoice", {
		onload_post_render(frm) {
			keepCompanyVisible(frm);
		},
		refresh(frm) {
			keepCompanyVisible(frm);
			restoreStandardDraftAction(frm);
		},
		after_save(frm) {
			restoreStandardDraftAction(frm, true);
		},
	});

	function keepCompanyVisible(frm) {
		if (!frm?.fields_dict?.company) return;

		const showCompany = () => {
			if (!frm.fields_dict.company) return;
			frm.set_df_property("company", "hidden", 0);
			frm.fields_dict.company.df.hidden = 0;
			frm.toggle_display("company", true);
			frm.refresh_field("company");
		};

		showCompany();
		frappe.after_ajax(showCompany);
		setTimeout(showCompany, 0);
		setTimeout(showCompany, 250);
	}

	function restoreStandardDraftAction(frm, forceClean = false) {
		if (!frm || cint(frm.doc?.docstatus) !== 0 || frm.doc?.__islocal) return;

		const savedAt = Date.now();
		[100, 500, 1200, 2500].forEach((delay) => {
			setTimeout(() => {
				if (!frm || cint(frm.doc?.docstatus) !== 0 || frm.doc?.__islocal) return;
				if (frm.__retail_local_draft_last_user_event_at > savedAt) return;

				if (forceClean) {
					frm.doc.__unsaved = 0;
				}
				if (!frm.doc.__unsaved) {
					frm.toolbar?.set_primary_action?.(false);
					frm.toolbar?.show_title_as_dirty?.();
				}
			}, delay);
		});
	}

	frappe.ui.form.on("Sales Invoice Item", {
		qty(frm, cdt, cdn) {
			updateFocQty(frm, cdt, cdn);
		},
		conversion_factor(frm, cdt, cdn) {
			updateFocQty(frm, cdt, cdn);
		},
		custom_foc_qty(frm, cdt, cdn) {
			updateFocQty(frm, cdt, cdn);
		},
	});

	function updateFocQty(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row || row.custom_total_stock_qty === undefined) return;

		const totalQty = flt(row.qty) + flt(row.custom_foc_qty);
		if (flt(row.custom_total_stock_qty) === totalQty) return;

		const values = {
			custom_total_stock_qty: totalQty,
		};

		frappe.model.set_value(cdt, cdn, values);
		frm.refresh_field("items");
	}
	})();

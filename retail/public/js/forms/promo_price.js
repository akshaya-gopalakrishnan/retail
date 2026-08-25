(function () {
	if (!window.frappe?.ui?.form) return;

	const PROMO_FIELDS = ["promo_price", "promo_price_including_tax", "discount_percent"];

	frappe.ui.form.on("Promo Price", {
		refresh(frm) {
			refreshPromoMethodLocks(frm);
		},
		onload_post_render(frm) {
			refreshPromoMethodLocks(frm);
		},
	});

	frappe.ui.form.on("Promo Price Item", {
		item(frm, cdt, cdn) {
			setDefaultUom(frm, cdt, cdn);
			lockPromoMethodFields(frm, cdt, cdn);
		},
		form_render(frm, cdt, cdn) {
			lockPromoMethodFields(frm, cdt, cdn);
		},
		promo_price(frm, cdt, cdn) {
			lockPromoMethodFields(frm, cdt, cdn);
		},
		promo_price_including_tax(frm, cdt, cdn) {
			lockPromoMethodFields(frm, cdt, cdn);
		},
		discount_percent(frm, cdt, cdn) {
			lockPromoMethodFields(frm, cdt, cdn);
		},
	});

	function refreshPromoMethodLocks(frm) {
		(frm.doc.products || []).forEach((row) => {
			lockPromoMethodFields(frm, row.doctype, row.name);
		});
	}

	function lockPromoMethodFields(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row) return;

		const selectedField = PROMO_FIELDS.find((fieldname) => flt(row[fieldname]));
		const gridRow = frm.fields_dict.products?.grid?.grid_rows_by_docname?.[cdn];
		if (!gridRow) {
			frm.refresh_field("products");
			return;
		}

		PROMO_FIELDS.forEach((fieldname) => {
			const field = gridRow.get_field(fieldname);
			if (!field) return;

			field.df.read_only = selectedField && selectedField !== fieldname ? 1 : 0;
			field.refresh();
		});
	}

	function setDefaultUom(frm, cdt, cdn) {
		const row = locals[cdt]?.[cdn];
		if (!row?.item || row.uom) return;

		frappe.db.get_value("Item", row.item, "stock_uom").then((response) => {
			const stockUom = response?.message?.stock_uom;
			if (!stockUom) return;

			frappe.model.set_value(cdt, cdn, "uom", stockUom);
			frm.refresh_field("products");
		});
	}
})();

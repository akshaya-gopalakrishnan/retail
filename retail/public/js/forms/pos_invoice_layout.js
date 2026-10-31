// Keep transaction values intact; simplify only the receipt form presentation.
frappe.ui.form.on("POS Invoice", {
	refresh(frm) {
		frm.layout.wrapper.addClass("retail-compact-pos-invoice");
		const submitted = frm.doc.docstatus !== 0;
		const same_currency = frm.doc.currency === frm.doc.__onload?.retail_company_currency;
		const has_value = value => Array.isArray(value) ? value.length > 0
			: value != null && value !== "" && value !== 0 && value !== "0";
		const optional_sections = {
			customer_po_details: ["po_no", "po_date"],
			pricing_rule_details: ["pricing_rules"],
			time_sheet_list: ["timesheets", "total_billing_amount"],
			advances_section: ["advances", "total_advance"],
			payment_schedule_section: ["payment_terms_template", "payment_schedule"],
			terms_section_break: ["tc_name", "terms"],
			loyalty_points_redemption: ["redeem_loyalty_points", "loyalty_points", "loyalty_amount"],
			section_break_49: ["discount_amount", "additional_discount_percentage", "coupon_code"],
			column_break4: ["write_off_amount"],
			more_information: ["campaign", "source", "inter_company_invoice_reference", "is_discounted"],
			sales_team_section_break: ["sales_partner", "commission_rate", "total_commission"],
			section_break2: ["sales_team"],
			subscription_section: ["from_date", "to_date", "auto_repeat"],
		};
		for (const [section, fields] of Object.entries(optional_sections)) {
			if (!frm.fields_dict[section]) continue;
			// Never hide a section containing a site-specific populated/required field.
			const section_fields = frm.fields_dict[section].fields_list || [];
			const used = fields.some(field => has_value(frm.doc[field])) ||
				section_fields.some(field => field.df.reqd ||
					(field.df.is_custom_field && has_value(frm.doc[field.df.fieldname])));
			frm.toggle_display(section, !submitted || used);
		}
		for (const name of ["base_total", "base_net_total", "base_grand_total",
			"base_rounding_adjustment", "base_paid_amount", "base_change_amount", "base_discount_amount"]) {
			const field = frm.fields_dict[name];
			if (!field) continue;
			if (field.df.retail_original_hidden == null) field.df.retail_original_hidden = field.df.hidden || 0;
			frm.set_df_property(name, "hidden", same_currency ? 1 : field.df.retail_original_hidden);
		}
		for (const name of ["scan_barcode", "last_scanned_warehouse"]) {
			if (frm.fields_dict[name]) frm.toggle_display(name, !submitted);
		}
		if (frm.fields_dict.is_pos) frm.toggle_display("is_pos", !submitted);
		if (frm.fields_dict.is_return) frm.toggle_display("is_return", !submitted || Boolean(frm.doc.is_return));
		for (const name of ["change_amount", "total_advance", "total_net_weight", "rounding_adjustment"]) {
			if (frm.fields_dict[name]) frm.toggle_display(name, !submitted || has_value(frm.doc[name]));
		}
		frm.layout.refresh_sections();
	},
});

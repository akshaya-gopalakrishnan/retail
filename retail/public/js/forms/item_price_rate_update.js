(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Item Price", {
		refresh(frm) {
			if (!["Standard Buying", "Standard Selling"].includes(frm.doc.price_list) || frm.doc.docstatus !== 0) return;
			frm.add_custom_button(__("Update Item Master Rate"), () => updateItemMasterRate(frm), __("Retail"));
		},
	});

	async function updateItemMasterRate(frm) {
		const preview = (await frappe.call({
			method: "retail.domains.item.rate_audit.get_item_price_rate_preview",
			args: { item_price: frm.doc.name },
		})).message;

		if (!preview?.changed) {
			frappe.msgprint(__("Item Master already has this rate."));
			return;
		}

		frappe.confirm(getPreviewMessage(preview), async () => {
			const result = await frappe.call({
				method: "retail.domains.item.rate_audit.apply_item_price_rate_update",
				args: { item_price: frm.doc.name },
				freeze: true,
				freeze_message: __("Updating Item Master Rate"),
			});
			frappe.show_alert({ message: __("Item Master rate updated: {0}", [result.message]), indicator: "green" });
		});
	}

	function getPreviewMessage(row) {
		return __(
			"Update Item Master {0} rate for {1} from {2} to {3}? This will affect future packing and pricing calculations.",
			[row.direction, row.item_code, format_currency(row.old_net_rate), format_currency(row.new_net_rate)]
		);
	}
})();

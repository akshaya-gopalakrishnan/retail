(function () {
	if (!window.frappe?.ui?.form) return;

	frappe.ui.form.on("Item", {
		validate(frm) {
			remove_empty_barcode_rows(frm);
		},
		before_save(frm) {
			remove_empty_barcode_rows(frm);
		},
	});

	function remove_empty_barcode_rows(frm) {
		if (!Array.isArray(frm.doc.barcodes) || !frm.doc.barcodes.length) return;

		let removed = false;
		for (let i = frm.doc.barcodes.length - 1; i >= 0; i--) {
			const row = frm.doc.barcodes[i];
			if (row.barcode) continue;

			if (row.doctype && row.name) {
				frappe.model.clear_doc(row.doctype, row.name);
			}
			frm.doc.barcodes.splice(i, 1);
			removed = true;
		}

		if (removed) {
			frm.refresh_field("barcodes");
		}
	}
})();

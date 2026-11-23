// Warehouse fetches add rows directly; refresh their display identity as well.
(() => {
    frappe.ui.form.on("Stock Reconciliation", {
        setup(frm) {
            const grid = frm.fields_dict.items.grid;
            const refresh = grid.refresh;
            grid.refresh = function (...args) {
                const result = refresh.apply(this, args);
                if (Number(frm.doc.docstatus) !== 0) return result;
                const signature = JSON.stringify((frm.doc.items || []).map(row =>
                    [row.name, row.item_code, row.uom, row.barcode, row.custom_packing_detail]));
                if (signature !== frm.__retail_reconciliation_identity) {
                    frm.__retail_reconciliation_identity = signature;
                    window.retail?.refresh_transaction_barcodes?.(frm);
                }
                return result;
            };
        },
        refresh(frm) {
            window.retail?.refresh_transaction_barcodes?.(frm);
        },
    });
})();

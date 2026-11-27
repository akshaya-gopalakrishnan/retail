// Keep selected/scanned packing barcodes in transaction item tables.
(() => {
    window.retail = window.retail || {};
    if (window.retail.transaction_barcodes) return;
    window.retail.transaction_barcodes = true;
    const parents = ["Quotation", "Sales Order", "Sales Invoice", "POS Invoice", "Delivery Note",
        "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Material Request",
        "Stock Entry", "Stock Reconciliation", "Supplier Quotation", "Request for Quotation"];
    const signature = row => JSON.stringify([row.item_code, row.uom, row.barcode, row.custom_packing_detail, row.custom_item_barcode]);
    const resolved = new WeakMap();
    // A packing search result already contains the permission-checked barcode.
    window.retail.remember_transaction_barcode = row => resolved.set(row, signature(row));
    async function refresh(frm) {
        if (frm.doc.docstatus !== 0) return;
        const generation = frm.__retail_barcode_generation = (frm.__retail_barcode_generation || 0) + 1;
        const rows = (frm.doc.items || []).filter(row => row.item_code &&
            frappe.meta.has_field(row.doctype, "custom_item_barcode") && resolved.get(row) !== signature(row));
        if (!rows.length) return;
        const snapshots = new Map(rows.map(row => [row.name, signature(row)]));
        const {message} = await frappe.call({method: "retail.transaction_barcodes.get_barcodes",
            args: {rows: rows.map(row => ({name: row.name, item_code: row.item_code, uom: row.uom,
                barcode: row.barcode, custom_packing_detail: row.custom_packing_detail,
                custom_item_barcode: row.custom_item_barcode}))}, no_spinner: true});
        if (generation !== frm.__retail_barcode_generation) return;
        let changed = false;
        for (const row of rows) {
            if (snapshots.get(row.name) !== signature(row) || !(row.name in (message || {}))) continue;
            if (row.custom_item_barcode !== message[row.name]) {
                row.custom_item_barcode = message[row.name];
                changed = true;
            }
            resolved.set(row, signature(row));
        }
        if (changed) frm.refresh_field("items");
    }
    function schedule(frm) {
        clearTimeout(frm.__retail_barcode_timer);
        frm.__retail_barcode_timer = setTimeout(() => {
            // Do not resolve an intermediate Item/UOM while native pricing runs.
            if (frm.__retail_purchase_action?.active) return schedule(frm);
            return refresh(frm);
        }, 100);
    }
    window.retail.refresh_transaction_barcodes = schedule;
    for (const parent of parents) {
        frappe.ui.form.on(parent, {refresh: schedule});
        // Stock tables use Detail/Item names; attach once metadata is available.
        frappe.ui.form.on(parent, {setup(frm) {
            for (const table of frm.meta.fields.filter(df => df.fieldtype === "Table")) {
                const child = table.options;
                const key = "__retail_barcode_" + child;
                if (window.retail[key] || !frappe.meta.has_field(child, "custom_item_barcode")) continue;
                window.retail[key] = true;
                frappe.ui.form.on(child, {
                    item_code(frm, cdt, cdn) {
                        const row = locals[cdt]?.[cdn];
                        if (row) {
                            const choice = row.__retail_packing_choice;
                            row.custom_packing_detail = choice?.packing_id || "";
                            row.custom_item_barcode = choice?.barcode || "";
                        }
                        schedule(frm);
                    },
                    uom: schedule, barcode: schedule,
                });
            }
        }});
    }
})();

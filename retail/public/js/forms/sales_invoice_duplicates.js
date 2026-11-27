// Ask before combining a newly entered Sales Invoice line with an existing line.
(() => {
    window.retail = window.retail || {};
    const protectedRow = row => ['sales_order', 'delivery_note', 'sales_invoice', 'serial_no',
        'batch_no', 'serial_and_batch_bundle', 'custom_foc_parent'].some(key => row[key]);
    const same = (a, b) => a !== b && a.item_code === b.item_code && !protectedRow(a) && !protectedRow(b)
        && ['uom', 'warehouse', 'custom_packing_detail', 'item_tax_template', 'pricing_rules'].every(key => (a[key] || '') === (b[key] || ''))
        && ['conversion_factor', 'rate', 'discount_percentage', 'discount_amount'].every(key => Number(a[key] || 0) === Number(b[key] || 0));
    const enabled = frm => frm.doc.doctype === 'Sales Invoice' && Number(frm.doc.docstatus || 0) === 0 && !frm.doc.is_return;
    async function removeDuplicate(frm, row) {
        if (!row || !enabled(frm) || !frm.doc.items.includes(row)) return;
        await frm.script_manager.trigger('before_items_remove', row.doctype, row.name);
        frappe.model.clear_doc(row.doctype, row.name);
        frm.doc.items = frm.doc.items.filter(item => item !== row);
        frm.doc.items.forEach((item, i) => { item.idx = i + 1; });
        await frm.script_manager.trigger('items_remove', row.doctype, row.name);
        frm.dirty();
        frm.refresh_field('items');
    }
    function offer(frm, existing, duplicate = null, initialQty = 1, matches = (a, b) => a.item_code === b.item_code
        && ['uom', 'warehouse', 'custom_packing_detail'].every(key => (a[key] || '') === (b[key] || ''))) {
        if (!enabled(frm) || frm.__retail_duplicate_dialog) return false;
        const valid = () => enabled(frm) && frm.doc.items.includes(existing)
            && (!duplicate || (frm.doc.items.includes(duplicate) && matches(existing, duplicate)));
        let accepted = false, applying = false;
        const duplicateCodes = new Set([duplicate?.item_code || "", existing.item_code]);
        const dialog = new frappe.ui.Dialog({
            title: __('Already added'),
            fields: [
                {fieldtype: 'HTML', fieldname: 'notice', options: `<p>${frappe.utils.escape_html(existing.item_name || existing.item_code)} — ${__('Already added in row {0}. Enter a positive quantity to add or a negative quantity to subtract.', [existing.idx])}</p>`},
                {fieldtype: 'Float', fieldname: 'qty', label: __('Quantity change'), default: initialQty, reqd: 1},
            ],
            primary_action_label: __('Update Quantity'),
            primary_action: async values => {
                const change = Number(values.qty);
                if (!Number.isFinite(change) || change === 0) { frappe.msgprint(__('Enter a positive quantity to add or a negative quantity to subtract.')); return; }
                const nextQty = Number(existing.qty || 0) + change;
                if (!(nextQty > 0)) { frappe.msgprint(__('The resulting item quantity must be greater than zero.')); return; }
                if (!valid()) { frappe.msgprint(__('The item or packing changed. Select the item again.')); return; }
                dialog.disable_primary_action();
                try {
                    applying = true;
                    await removeDuplicate(frm, duplicate);
                    await frappe.model.set_value(existing.doctype, existing.name, 'qty', nextQty);
                    accepted = true;
                    frm.dirty();
                    frm.refresh_field('items');
                    dialog.hide();
                } finally { applying = false; dialog.enable_primary_action(); }
            },
        });
        frm.__retail_duplicate_dialog = dialog;
        dialog.on_hide = () => {
            if (frm.__retail_duplicate_dialog === dialog) delete frm.__retail_duplicate_dialog;
            // Pricing/UOM callbacks may have changed the row since the popup
            // opened. Cancellation owns this newly entered row, not its price.
            if (!accepted && !applying && duplicate && duplicateCodes.has(duplicate.item_code || "")) {
                dialog.__retail_cleanup = removeDuplicate(frm, duplicate).catch(error => {
                    frappe.msgprint(__("Could not remove the duplicate row. Please remove it from the Items table."));
                    console.error(error);
                });
            }
        };
        dialog.show();
        return true;
    }
    // Packing search already knows the identity: detect duplicates before pricing.
    function preflight(frm, row, choice) {
        if (!enabled(frm) || (row && protectedRow(row))) return false;
        const existing = frm.doc.items.find(other => other !== row && !protectedRow(other)
            && other.item_code === choice.item_code && other.uom === choice.uom
            && (other.custom_packing_detail || '') === (choice.packing_id || '')
            && (!row?.warehouse || other.warehouse === row.warehouse));
        if (!existing) return false;
        const originalCode = row?.item_code || '';
        return offer(frm, existing, row, Number(row?.qty) > 0 ? Number(row.qty) : 1,
            (original, added) => [(originalCode || ''), choice.item_code].includes(added.item_code || '')
                && original.item_code === choice.item_code && original.uom === choice.uom
                && (original.custom_packing_detail || '') === (choice.packing_id || ''));
    }
    function schedule(frm, row) {
        if (!enabled(frm) || !row?.item_code) return;
        const pending = frm.__retail_duplicate_checks ||= new Map();
        clearTimeout(pending.get(row.name));
        pending.set(row.name, setTimeout(async () => {
            await frappe.after_ajax();
            if (!pending.has(row.name)) return;
            if (frm.__retail_purchase_action?.active || row.__retail_vat_syncing || row.__retail_selecting_packing) {
                schedule(frm, row); return;
            }
            pending.delete(row.name);
            if (!enabled(frm) || !frm.doc.items.includes(row)) return;
            const existing = frm.doc.items.find(other => Number(other.idx) < Number(row.idx) && same(other, row));
            if (existing) offer(frm, existing, row, Number(row.qty) > 0 ? Number(row.qty) : 1);
        }, 200));
    }
    frappe.ui.form.on('Sales Invoice', {refresh(frm) {
        const manager = frm.script_manager;
        if (manager.__retail_duplicate_items) return;
        manager.__retail_duplicate_items = true;
        const trigger = manager.trigger;
        manager.trigger = function (event, cdt, cdn, ...args) {
            const entering = locals[cdt]?.[cdn];
            if (event === 'item_code' && cdt === 'Sales Invoice Item' && entering?.item_code
                && !entering.__retail_selecting_packing && !entering.item_name
                && preflight(frm, entering, {item_code: entering.item_code, uom: entering.uom, packing_id: entering.custom_packing_detail || ''})) {
                return Promise.resolve();
            }
            const result = trigger.call(this, event, cdt, cdn, ...args);
            if (cdt !== 'Sales Invoice Item') return result;
            return Promise.resolve(result).then(value => {
                const row = locals[cdt]?.[cdn];
                if (event === 'item_code' || (frm.__retail_duplicate_checks?.has(cdn) && ['uom', 'barcode'].includes(event))) schedule(frm, row);
                return value;
            });
        };
    }});
    window.retail.sales_invoice_duplicates = {same, offer, preflight};
})();

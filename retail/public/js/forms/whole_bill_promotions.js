// Whole Bill qualification can change the winning promotion on every row.
(() => {
    function protectQuantityEditor(frm) {
        if (!frm.wrapper?.addEventListener || frm.__retail_qty_editor) return;
        frm.__retail_qty_editor = true;
        frm.wrapper.addEventListener("focus", event => {
            const input = event.target;
            if (!input.matches('input[data-fieldname="qty"]')) return;
            const name = input.closest(".grid-row")?.getAttribute("data-name");
            const row = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[name];
            const field = [row?.on_grid_fields_dict?.qty, row?.grid_form?.fields_dict?.qty]
                .find(control => control?.$input?.[0] === input);
            if (!field || field.__retail_qty_editor) return;
            field.__retail_qty_editor = true;
            let draft;
            input.addEventListener("input", () => { draft = input.value; });
            // Clear before native change handlers commit and normalize the value.
            input.addEventListener("change", () => { draft = undefined; }, true);
            input.addEventListener("blur", () => { draft = undefined; }, true);
            const refresh = field.refresh;
            field.refresh = function (...args) {
                const editing = draft !== undefined && document.activeElement === input;
                const selection = [input.selectionStart, input.selectionEnd];
                const result = refresh.apply(this, args);
                if (editing && input.isConnected && document.activeElement === input) {
                    input.value = draft;
                    if (selection[0] !== null) input.setSelectionRange(...selection);
                }
                return result;
            };
        }, true);
    }
    const enabled = frm => frappe.boot.retail_has_whole_bill_promotions &&
        frm.doc.docstatus === 0 && !frm.doc.is_return && !frm.doc.is_consolidated && !frm.doc.is_pos;
    function displays(frm) {
        clearTimeout(frm.__retail_promo_display_timer);
        frm.__retail_promo_display_timer = setTimeout(async () => {
            await frappe.after_ajax();
            await window.retail.transaction_items.refreshVatDisplays?.(frm);
        }, 100);
    }
    function schedule(frm) {
        if (!enabled(frm)) return;
        clearTimeout(frm.__retail_whole_bill_timer);
        frm.__retail_whole_bill_timer = setTimeout(async () => {
            await frappe.after_ajax();
            await frm.cscript.apply_pricing_rule(undefined, true);
        }, 150);
    }
    for (const parent of ["Sales Invoice", "Delivery Note"]) {
        frappe.ui.form.on(parent, {refresh(frm) {
            protectQuantityEditor(frm);
            if (frm.cscript.__retail_whole_bill) return;
            const apply = frm.cscript.apply_pricing_rule;
            if (!apply) return;
            frm.cscript.__retail_whole_bill = true;
            frm.cscript.apply_pricing_rule = function (item, calculate, ...rest) {
                const result = apply.call(this, enabled(frm) ? undefined : item, calculate, ...rest);
                if (enabled(frm)) Promise.resolve(result).then(() => displays(frm));
                return result;
            };
        }});
        frappe.ui.form.on(parent + " Item", {
            item_code: schedule, qty: schedule, uom: schedule,
            price_list_rate: schedule, items_remove: schedule,
        });
    }
})();

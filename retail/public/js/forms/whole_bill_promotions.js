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
    function packingBusy(frm) {
        return (frm.__retail_selecting_count || 0) > 0
            || (frm.doc.items || []).some(row => row.__retail_selecting_packing);
    }
    function rowSignature(frm) {
        return new Map((frm.doc.items || []).filter(row => row?.name).map(row => [row.name, {
            qty: row.qty, rate: row.rate,
            discount_percentage: row.discount_percentage, discount_amount: row.discount_amount,
            pricing_rules: row.pricing_rules || "", margin_type: row.margin_type || "",
            margin_rate_or_amount: row.margin_rate_or_amount,
        }]));
    }
    const num = value => {
        const parsed = typeof flt === "function" ? flt(value) : Number(value || 0);
        return Number.isFinite(parsed) ? parsed : 0;
    };
    // A pricing-rule name can change while the unit rate the user calculated stays.
    // Only a real discount or margin change may replace that rate.
    function discountUnchanged(next, prev) {
        if (!prev) return false;
        return num(next.discount_percentage) === num(prev.discount_percentage)
            && num(next.discount_amount) === num(prev.discount_amount)
            && (next.margin_type || "") === (prev.margin_type || "")
            && num(next.margin_rate_or_amount) === num(prev.margin_rate_or_amount);
    }
    function restorePricedRows(frm, before) {
        const grid = frm.fields_dict?.items?.grid;
        let changed = false;
        for (const [name, prev] of before) {
            const row = (frm.doc.items || []).find(item => item.name === name);
            if (!row) continue;
            const fields = [];
            if (num(row.qty) !== num(prev.qty)) { row.qty = prev.qty; fields.push("qty"); }
            if (discountUnchanged(row, prev) && num(row.rate) !== num(prev.rate)) {
                row.rate = prev.rate;
                fields.push("rate");
            }
            for (const field of fields) grid?.grid_rows_by_docname?.[name]?.refresh_field?.(field);
            changed = changed || fields.length > 0;
        }
        if (changed) frm.cscript?.calculate_taxes_and_totals?.();
    }
    function schedule(frm) {
        if (!enabled(frm)) return;
        clearTimeout(frm.__retail_whole_bill_timer);
        const generation = frm.__retail_price_generation = (frm.__retail_price_generation || 0) + 1;
        frm.__retail_whole_bill_timer = setTimeout(async () => {
            await frappe.after_ajax();
            if (generation !== frm.__retail_price_generation) return;
            // A full-bill pass sends every line. Starting it while the next item
            // is still loading makes each added row wait on a larger request.
            if (frappe.request?.ajax_count || frm.__retail_purchase_action?.active || packingBusy(frm)) {
                schedule(frm);
                return;
            }
            const before = rowSignature(frm);
            frm.__retail_price_snapshot = before;
            frm.__retail_expect_pricing_token = generation;
            try {
                await frm.cscript.apply_pricing_rule(undefined, true);
            } finally {
                if (frm.__retail_price_snapshot === before) delete frm.__retail_price_snapshot;
            }
            if (generation !== frm.__retail_price_generation) return;
            // The pricing response writes the price-list rate back onto every row.
            // Keep the quantity and unit rate the user just calculated unless the
            // promotion itself changed the discount.
            restorePricedRows(frm, before);
        }, 150);
    }
    for (const parent of ["Sales Invoice", "Delivery Note"]) {
        frappe.ui.form.on(parent, {refresh(frm) {
            protectQuantityEditor(frm);
            if (frm.cscript.__retail_whole_bill) return;
            const apply = frm.cscript.apply_pricing_rule;
            if (!apply) return;
            frm.cscript.__retail_whole_bill = true;
            if (typeof frm.cscript._set_values_for_item_list === "function" && !frm.cscript.__retail_price_guard) {
                frm.cscript.__retail_price_guard = true;
                const setValues = frm.cscript._set_values_for_item_list;
                frm.cscript._set_values_for_item_list = function (children) {
                    const before = frm.__retail_price_snapshot;
                    if (!before) return setValues.call(this, children);
                    const copy = (children || []).map(child => {
                        const next = {...child};
                        const prev = before.get(child.name);
                        // Native copies price_list_rate onto rate, which puts the list
                        // price back after the quantity calculation has already displayed.
                        delete next.price_list_rate;
                        delete next.qty;
                        if (!prev) return next;
                        if (discountUnchanged(next, prev)) delete next.rate;
                        return next;
                    });
                    return setValues.call(this, copy);
                };
            }
            if (typeof frm.call === "function" && !frm.__retail_pricing_guard) {
                frm.__retail_pricing_guard = true;
                const call = frm.call;
                frm.call = function (opts, ...args) {
                    const method = typeof opts === "object" ? String(opts?.method || "") : "";
                    if (opts?.callback && method.includes("apply_pricing_rule") && frm.__retail_expect_pricing_token) {
                        const token = frm.__retail_expect_pricing_token;
                        delete frm.__retail_expect_pricing_token;
                        const original = opts.callback;
                        opts.callback = function (...cbArgs) {
                            if ((frm.__retail_price_generation || 0) !== token) return;
                            return original.apply(this, cbArgs);
                        };
                    }
                    return call.call(this, opts, ...args);
                };
            }
            frm.cscript.apply_pricing_rule = function (item, calculate, ...rest) {
                // Price the row that just changed immediately. The whole bill is
                // evaluated once entry is idle, because its result can replace
                // the winning promotion on earlier rows.
                if (enabled(frm) && item) schedule(frm);
                const result = apply.call(this, item, calculate, ...rest);
                if (enabled(frm) && !item) Promise.resolve(result).then(() => displays(frm));
                return result;
            };
        }});
        frappe.ui.form.on(parent + " Item", {
            item_code: schedule, uom: schedule,
            price_list_rate: schedule, items_remove: schedule,
        });
    }
})();

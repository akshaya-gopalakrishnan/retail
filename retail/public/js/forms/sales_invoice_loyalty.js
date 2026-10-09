/* Secure ledger lookup and live totals; saving/submitting validates again on the server. */
(() => {
    const field = "custom_available_loyalty_points";
    const context = frm => [frm.doc.name, frm.doc.customer, frm.doc.company,
        frm.doc.loyalty_program, frm.doc.posting_date].join("|");

    async function refreshBalance(frm) {
        if (!frm.fields_dict[field] || frm.doc.is_consolidated) return;
        const request = (frm.__retail_loyalty_request || 0) + 1;
        frm.__retail_loyalty_request = request;
        const key = context(frm);
        frm.__retail_loyalty_context = null;
        frm.redemption_conversion_factor = 0;
        frm.doc[field] = 0;
        frm.refresh_field(field);
        if (!frm.doc.customer || !frm.doc.company) return;
        const { message } = await frappe.call({
            method: "retail.loyalty.get_available_points",
            args: { customer: frm.doc.customer, company: frm.doc.company,
                loyalty_program: frm.doc.loyalty_program, posting_date: frm.doc.posting_date },
        });
        if (request !== frm.__retail_loyalty_request || key !== context(frm)) return;
        frm.doc[field] = cint(message.available_points);
        frm.redemption_conversion_factor = flt(message.conversion_factor);
        if (frm.doc.docstatus === 0 && !frm.doc.is_return) {
            frm.doc.loyalty_program = message.loyalty_program || null;
            frm.refresh_field("loyalty_program");
        }
        frm.__retail_loyalty_context = context(frm);
        frm.refresh_field(field);
        if (frm.doc.docstatus === 0) {
            if (frm.doc.is_return) await refreshReturn(frm);
            else await updateRedemption(frm);
        }
        showRemaining(frm);
    }

    function showRemaining(frm) {
        const remaining = cint(frm.doc[field]) - (frm.doc.docstatus === 0 && !frm.doc.is_return &&
            frm.doc.redeem_loyalty_points ? cint(frm.doc.loyalty_points) : 0);
        frm.set_df_property(field, "description", frm.doc.docstatus === 0 && !frm.doc.is_return
            ? __("Points remaining after this redemption: {0}", [remaining])
            : __("Current available ledger balance."));
    }

    async function updateRedemption(frm) {
        if (frm.doc.docstatus !== 0 || frm.doc.is_consolidated) return;
        if (frm.doc.is_return) return refreshReturn(frm);
        if (!frm.doc.redeem_loyalty_points) {
            await frm.set_value({ loyalty_points: 0, loyalty_amount: 0 });
            showRemaining(frm);
            return;
        }
        if (frm.__retail_loyalty_context !== context(frm)) return refreshBalance(frm);
        const points = flt(frm.doc.loyalty_points);
        if (points < 0 || !Number.isInteger(points) || points > cint(frm.doc[field])) {
            await frm.set_value("loyalty_amount", 0);
            showRemaining(frm);
            frappe.throw(__("Enter whole loyalty points between 0 and {0}.", [cint(frm.doc[field])]));
        }
        const amount = flt(points * frm.redemption_conversion_factor, precision("loyalty_amount", frm.doc));
        const total = frm.doc.disable_rounded_total ? flt(frm.doc.grand_total) : flt(frm.doc.rounded_total);
        const limit = (total - flt(frm.doc.total_advance) - flt(frm.doc.write_off_amount)) * flt(frm.doc.conversion_rate);
        if (amount > Math.max(0, flt(limit, precision("loyalty_amount", frm.doc)))) {
            frappe.throw(__("The loyalty redemption amount exceeds the remaining invoice amount."));
        }
        await frm.set_value("loyalty_amount", amount);
        showRemaining(frm);
    }

    async function refreshReturn(frm) {
        if (!frm.doc.is_return || frm.doc.docstatus !== 0 || !frm.doc.return_against) return;
        const key = `${context(frm)}|${frm.doc.return_against}|${frm.doc.grand_total}`;
        const request = (frm.__retail_return_request || 0) + 1;
        frm.__retail_return_request = request;
        const { message } = await frappe.call({
            method: "retail.loyalty.get_return_preview",
            args: { return_against: frm.doc.return_against, grand_total: frm.doc.grand_total,
                invoice: frm.is_new() ? null : frm.doc.name },
        });
        if (request !== frm.__retail_return_request ||
            key !== `${context(frm)}|${frm.doc.return_against}|${frm.doc.grand_total}`) return;
        // Avoid recursive point handlers while applying the server's return calculation.
        frm.__retail_applying_return = true;
        try { await frm.set_value(message); }
        finally { frm.__retail_applying_return = false; }
    }

    // Replace just the core loyalty handlers; retain its loyalty_amount totals handler.
    ["loyalty_points", "redeem_loyalty_points", "get_loyalty_details", "set_loyalty_points"]
        .forEach(event => frappe.ui.form.off("Sales Invoice", event));
    frappe.ui.form.on("Sales Invoice", {
        refresh(frm) {
            frm.set_df_property("loyalty_points", "read_only", !!frm.doc.is_return);
            frm.set_df_property("redeem_loyalty_points", "read_only", !!frm.doc.is_return);
            return refreshBalance(frm);
        },
        customer(frm) {
            // The previous customer's fetched program may still be on the form.
            frm.doc.loyalty_program = null;
            return refreshBalance(frm);
        },
        company: refreshBalance,
        loyalty_program: refreshBalance,
        posting_date: refreshBalance,
        loyalty_points(frm) { if (!frm.__retail_applying_return) return updateRedemption(frm); },
        redeem_loyalty_points(frm) { if (!frm.__retail_applying_return) return updateRedemption(frm); },
        get_loyalty_details: refreshBalance,
        set_loyalty_points: updateRedemption,
        grand_total(frm) { if (frm.doc.is_return) return refreshReturn(frm); },
        async validate(frm) {
            await refreshBalance(frm);
            if (frm.doc.redeem_loyalty_points && !frm.doc.is_return &&
                frm.__retail_loyalty_context !== context(frm)) {
                frappe.throw(__("Refresh the loyalty balance before saving."));
            }
        },
    });
})();

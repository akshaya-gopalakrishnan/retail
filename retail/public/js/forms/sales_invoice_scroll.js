// Preserve the working position while item rows are rebuilt.
(() => {
    function snapshot(grid) {
        const nodes = new Set();
        let node = grid.wrapper?.[0];
        if (!node) return [];
        node.querySelectorAll('.form-grid-container').forEach(element => nodes.add(element));
        while (node) {
            nodes.add(node);
            node = node.parentElement;
        }
        if (document.scrollingElement) nodes.add(document.scrollingElement);
        return [...nodes].map(element => ({element, top: element.scrollTop, left: element.scrollLeft}));
    }
    function restore(positions) {
        for (const {element, top, left} of positions) {
            if (element.scrollTop !== top) element.scrollTop = top;
            if (element.scrollLeft !== left) element.scrollLeft = left;
        }
    }
    function install(frm) {
        const grid = frm.fields_dict.items?.grid;
        if (!grid || grid.__retail_keep_position) return;
        grid.__retail_keep_position = true;
        const refresh = grid.refresh;
        grid.refresh = function (...args) {
            const positions = snapshot(this);
            try { return refresh.apply(this, args); }
            finally { restore(positions); }
        };
        const nativeFocus = grid.set_focus_on_row;
        grid.set_focus_on_row = function (idx) {
            if (!this.allow_on_grid_editing()) return nativeFocus.call(this, idx);
            // Resolve the row after the native refresh/add work has completed.
            setTimeout(() => {
                const row = this.grid_rows[idx == null ? this.grid_rows.length - 1 : idx];
                if (!row) return;
                const positions = snapshot(this);
                row.toggle_editable_row(true);
                const input = row.row.find('input[type="Text"],textarea,select').filter(':visible:first')[0];
                input?.focus({preventScroll: true});
                restore(positions);
            }, 100);
        };
    }
    for (const doctype of ['Purchase Order', 'Purchase Receipt', 'Purchase Invoice', 'Sales Invoice', 'Delivery Note']) {
        frappe.ui.form.on(doctype, {refresh: install});
    }
})();

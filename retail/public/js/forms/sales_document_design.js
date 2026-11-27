// Shared presentation only: table fields, ordering, widths and handlers stay native.
(() => {
    if (!document.getElementById('retail-sales-document-design')) {
        const style = document.createElement('style');
        style.id = 'retail-sales-document-design';
        style.textContent = `
            .retail-sales-document-design .form-grid { border-radius: var(--border-radius-md); }
            .retail-sales-document-design .grid-heading-row { background: var(--control-bg); font-weight: 600; }
            .retail-sales-document-design .grid-body .data-row { min-height: 38px; }
            .retail-sales-document-design .grid-body .grid-row:nth-child(odd):not(.editable-row) .data-row { background: var(--subtle-fg); }
            .retail-sales-document-design .form-section .section-head { font-weight: 600; }
        `;
        document.head.appendChild(style);
    }
    for (const doctype of ['Sales Invoice', 'Delivery Note']) frappe.ui.form.on(doctype, {
        refresh(frm) { frm.wrapper.classList.add('retail-sales-document-design'); },
    });
})();

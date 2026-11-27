// Use the exact paginated PDF for the two numbered A4 document formats.
(() => {
    const proto = frappe.ui.form.PrintView.prototype;
    if (proto.__retail_numbered_documents) return;
    proto.__retail_numbered_documents = true;
    const render = proto.render_page;
    proto.render_page = function (method, printit = false) {
        const format = this.get_print_format();
        if (printit && method === '/printview?' && format.pdf_generator === 'retail-numbered'
            && ['Sales Invoice - A4', 'Delivery Note - A4'].includes(format.name)) {
            return render.call(this, '/api/method/frappe.utils.print_format.download_pdf?', false);
        }
        return render.call(this, method, printit);
    };
})();

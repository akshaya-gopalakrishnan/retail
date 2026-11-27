const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
test('only numbered A4 paper printing uses the numbered PDF; native routes remain intact',()=>{
    const calls=[];
    class PrintView {render_page(method,printit){calls.push({method,printit});return 'native';}get_print_format(){return this.format;}}
    const context={frappe:{ui:{form:{PrintView}}}};
    const source=fs.readFileSync(path.join(__dirname,'../public/js/printing/numbered_documents.js'),'utf8');
    vm.runInNewContext(source,context);const wrapper=PrintView.prototype.render_page;
    vm.runInNewContext(source,context);assert.equal(PrintView.prototype.render_page,wrapper);
    const view=new PrintView();
    for (const name of ['Sales Invoice - A4','Delivery Note - A4']) {
        view.format={name,pdf_generator:'retail-numbered'};
        assert.equal(view.render_page('/printview?',true),'native');
        assert.equal(calls.pop().method,'/api/method/frappe.utils.print_format.download_pdf?');
    }
    view.format={name:'Other Format',pdf_generator:'wkhtmltopdf'};
    view.render_page('/printview?',true);assert.equal(calls.pop().method,'/printview?');
    view.render_page('/api/method/frappe.utils.print_format.download_pdf?',false);assert.equal(calls.pop().printit,false);
});

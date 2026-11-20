/* One editable conversion grid, with consumption details available per row. */
(() => {
    const method = 'retail.product_conversion.';
    function setupMaterialDisplay(frm) {
        const grid=frm.fields_dict.items.grid;
        const formatter=(value, field, options, row)=>{
            const materials=(frm.doc.materials||[]).filter(material=>
                material.row_key && material.row_key===row?.row_key && material.item_code);
            if(!materials.length)return frappe.form.formatters.Link(value,field,options,row);
            const codes=[...new Set(materials.map(material=>material.item_code))];
            // Display the conversion's actual consumption, including extra BOM
            // materials and saved edits, without replacing the primary item value.
            return codes.map(code=>{
                const material=materials.find(material=>material.item_code===code);
                const name=material.item_name || frappe.utils.get_link_title('Item',code);
                const label=name && name!==code ? `${code} - ${name}` : code;
                return frappe.form.formatters.Link(code,field,{...options,label},row);
            }).join(', ');
        };
        grid.update_docfield_property('main_item','formatter',formatter);
        for(const [field] of grid.visible_columns||[]){
            if(field.fieldname==='main_item')field.formatter=formatter;
        }
        if(!frm.__pc_material_style){
            frm.__pc_material_style=$('<style>').text(`
                .pc-material-display .grid-body [data-fieldname="main_item"] .static-area {
                    white-space: normal !important; overflow: visible; height: auto;
                    overflow-wrap: anywhere;
                }
            `).appendTo(frm.wrapper);
        }
        grid.wrapper.addClass('pc-material-display');
    }
    function setupSections(frm) {
        for(const name of ['staff_section','costs_section']){
            const section=frm.layout.sections_dict[name];
            // Keep the user's open/closed choice during normal field refreshes.
            if(section)section.df.collapsible_depends_on=()=>!section.is_collapsed();
        }
    }
    function setupRemarks(frm) {
        const input=frm.fields_dict.remarks?.$input?.[0];
        if(!input || input.tagName!=='TEXTAREA')return;
        input.rows=1;
        input.style.setProperty('min-height','32px','important');
        input.style.resize='vertical';
        input.style.overflowY='hidden';
        const grow=()=>{
            if(!input.getClientRects().length)return;
            input.style.height='0px';
            const style=getComputedStyle(input);
            const border=parseFloat(style.borderTopWidth)+parseFloat(style.borderBottomWidth);
            input.style.height=Math.max(32,input.scrollHeight+border)+'px';
        };
        $(input).off('input.pcRemarks').on('input.pcRemarks',grow);
        frm.__pc_remarks_observer?.disconnect();
        let width;
        frm.__pc_remarks_observer=new ResizeObserver(entries=>{
            const next=entries[0].contentRect.width;
            if(next===width)return;
            width=next;requestAnimationFrame(grow);
        });
        frm.__pc_remarks_observer.observe(input);
        grow();
    }
    async function callDoc(frm, name, values) {
        await frm.call({doc: frm.doc, method: name, args: values ? {values} : {},
            freeze: true, freeze_message: __('Calculating conversion...')});
        frm.refresh_fields(); frm.dirty();
        if((frm.doc.items||[]).some(r=>r.item_code))frm.add_custom_button(__('Consumption Details'),()=>consumptionDetails(frm));
    }
    function itemQuery() { return {filters: {is_stock_item: 1, disabled: 0, has_variants: 0}}; }
    function consumptionDetails(frm, row) {
        if (!row) {
            const products=(frm.doc.items||[]).filter(r=>r.item_code);
            if (!products.length) return frappe.msgprint(__('Add an item row first.'));
            if (products.length===1) return consumptionDetails(frm,products[0]);
            const select=new frappe.ui.Dialog({title:__('Consumption Details'),fields:[
                {fieldname:'product',label:__('Packing Item'),fieldtype:'Select',reqd:1,
                    options:products.map(r=>({label:`${r.idx}: ${r.item_name||r.item_code}`,value:r.row_key}))},
            ],primary_action_label:__('Open'),primary_action:values=>{
                select.hide();consumptionDetails(frm,products.find(r=>r.row_key===values.product));
            }});retail.keyboard.bind_dialog(select);return select.show();
        }
        let data=(frm.doc.materials||[]).filter(r=>r.row_key===row.row_key).map(r=>({...r}));
        if(!data.length && row.main_item)data=[{item_code:row.main_item,qty:flt(row.main_qty),warehouse:frm.doc.source_warehouse,
            current_stock:row.main_stock_qty,unit_cost:row.main_unit_cost}];
        const editable=frm.doc.docstatus===0;
        const pending=new Set();
        const requests=new WeakMap();
        const failed=new WeakSet();
        function refreshMaterial() {
            const material=this.grid_row.doc;
            const grid=this.grid;
            const code=material.item_code;
            const warehouse=material.warehouse || frm.doc.source_warehouse;
            material.warehouse=warehouse;
            material.batch_no=null;material.serial_no=null;
            material.current_stock=null;material.unit_cost=null;
            const token={};requests.set(material,token);failed.delete(material);
            this.grid_row.refresh();
            if(!code || !warehouse)return;
            const task=Promise.resolve(frappe.call({method:method+'get_stock_details',args:{item_code:code,warehouse,company:frm.doc.company}}))
                .then(({message})=>{
                    if(requests.get(material)!==token || !grid.get_data().includes(material))return;
                    Object.assign(material,{current_stock:message.current_stock,unit_cost:message.stock_cost,
                        item_name:message.item_name,stock_uom:message.stock_uom});
                    grid.grid_rows.find(row=>row.doc===material)?.refresh();
                }).catch(()=>{
                    if(requests.get(material)===token)failed.add(material);
                }).finally(()=>pending.delete(task));
            pending.add(task);
        }
        const dialog=new frappe.ui.Dialog({title:__('Consumption for {0}',[row.item_name||row.item_code]),size:'extra-large',fields:[
            {fieldname:'lines',fieldtype:'Table',label:__('Materials'),data,in_place_edit:true,cannot_add_rows:!editable,cannot_delete_rows:!editable,
                fields:[
                    {fieldname:'item_code',label:__('Item'),fieldtype:'Link',options:'Item',reqd:1,in_list_view:1,columns:2,read_only:!editable,get_query:itemQuery,change:refreshMaterial},
                    {fieldname:'qty',label:__('Quantity'),fieldtype:'Float',reqd:1,in_list_view:1,columns:1,read_only:!editable},
                    {fieldname:'warehouse',label:__('Warehouse'),fieldtype:'Link',options:'Warehouse',reqd:1,default:frm.doc.source_warehouse,in_list_view:1,columns:2,read_only:!editable,
                        get_query:()=>({filters:{company:frm.doc.company,is_group:0,disabled:0}}),change:refreshMaterial},
                    {fieldname:'current_stock',label:__('Current Stock'),fieldtype:'Float',in_list_view:1,columns:1,read_only:1},
                    {fieldname:'unit_cost',label:__('Stock Cost / Unit'),fieldtype:'Currency',options:frm.doc.currency,in_list_view:1,columns:2,read_only:1},
                    {fieldname:'batch_no',label:__('Batch'),fieldtype:'Link',options:'Batch',in_list_view:1,columns:2,read_only:!editable,
                        get_query:material=>({query:'erpnext.controllers.queries.get_batch_no',filters:{item_code:material.item_code,warehouse:material.warehouse||frm.doc.source_warehouse,posting_date:frm.doc.posting_date}})},
                    {fieldname:'serial_no',label:__('Serial Numbers'),fieldtype:'Small Text',read_only:!editable},
                ]},
        ],primary_action_label:editable?__('Apply'):__('Close'),primary_action:async()=>{
            await Promise.all([...pending]);
            if(dialog.fields_dict.lines.grid.get_data().some(material=>failed.has(material)))return frappe.msgprint(__('Stock details could not be loaded. Reselect the material or warehouse and try again.'));
            if(editable)await callDoc(frm,'update_consumption',{row_key:row.row_key,rows:dialog.fields_dict.lines.grid.get_data()});
            dialog.hide();
        }});retail.keyboard.bind_dialog(dialog);dialog.show();
    }
    function addProduct(frm, source) {
        const dialog = new frappe.ui.Dialog({title: source === 'BOM' ? __('Get Items from BOM') : __('From Main Item'),
            fields: [
                {fieldname:'source_type',fieldtype:'Data',default:source,hidden:1},
                {fieldname:'bom_no',label:__('BOM'),fieldtype:'Link',options:'BOM',reqd:source==='BOM',hidden:source!=='BOM',
                    get_query:()=>({filters:{company:frm.doc.company,docstatus:1,is_active:1}})},
                {fieldname:'use_multi_level_bom',label:__('Use Multi-Level BOM'),fieldtype:'Check',default:1,hidden:source!=='BOM'},
                {fieldname:'main_item',label:__('Main Stock Item'),fieldtype:'Link',options:'Item',reqd:source==='Main Item',hidden:source!=='Main Item',get_query:itemQuery,
                    onchange:async()=>{
                        const field=dialog.fields_dict.main_item;
                        const code=field.value || dialog.get_value('main_item');
                        if(!code)return;
                        const {message}=await frappe.call({method:method+'get_stock_details',args:{item_code:code,warehouse:frm.doc.source_warehouse,company:frm.doc.company}});
                        if((field.value || dialog.get_value('main_item'))!==code)return;
                        dialog.fields_dict.stock_info.df.options=`<div class="alert alert-info">${__('Current Stock')}: <b>${frappe.utils.escape_html(String(message.current_stock))} ${frappe.utils.escape_html(message.stock_uom)}</b><br>${__('Stock Cost / Unit')}: <b>${format_currency(message.stock_cost,frm.doc.currency)}</b></div>`;
                        dialog.fields_dict.stock_info.refresh();
                    }},
                {fieldname:'stock_info',fieldtype:'HTML',hidden:source!=='Main Item'},
                {fieldname:'item_code',label:__('Finished Packing Item'),fieldtype:'Link',options:'Item',reqd:source==='Main Item',hidden:source!=='Main Item',get_query:itemQuery},
                {fieldname:'qty',label:__('Quantity to Generate'),fieldtype:'Float',reqd:1,default:1},
                {fieldname:'qty_per_unit',label:__('Main Item Consumption per Finished Unit'),fieldtype:'Float',reqd:source==='Main Item',hidden:source!=='Main Item'},
                {fieldname:'labour_cost',label:__('Labour Cost (Total)'),fieldtype:'Currency',options:frm.doc.currency,default:0},
                {fieldname:'packing_cost',label:__('Extra Packing Cost (Total)'),fieldtype:'Currency',options:frm.doc.currency,default:0},
                {fieldname:'update_item_master',label:__('Update Item Master Cost'),fieldtype:'Check',default:0},
            ], primary_action_label:__('Get Items'),primary_action:async values=>{
                await callDoc(frm,'add_product',values);dialog.hide();
            }});
        retail.keyboard.bind_dialog(dialog);
        dialog.show();
    }
    async function defaults(frm) {
        if(!frm.doc.company || frm.doc.docstatus)return;
        const {message}=await frappe.call({method:method+'get_defaults',args:{company:frm.doc.company}});
        await frm.set_value(message);
    }
    function view(frm,label,report,extra={}) {
        frm.add_custom_button(__(label),()=>{
            frappe.route_options={company:frm.doc.company,from_date:frm.doc.posting_date,
                to_date:frappe.datetime.get_today(),voucher_no:frm.doc.stock_entry,
                show_cancelled_entries:frm.doc.docstatus===2,ignore_prepared_report:true,...extra};
            frappe.set_route('query-report',report);
        },__('View'));
    }
    frappe.ui.form.on('Product Conversion',{
        setup(frm){
            for(const field of ['source_warehouse','target_warehouse'])frm.set_query(field,()=>({filters:{company:frm.doc.company,is_group:0,disabled:0}}));
            for(const field of ['labour_account','packing_account'])frm.set_query(field,()=>({filters:{company:frm.doc.company,root_type:'Expense',is_group:0,disabled:0,account_currency:frm.doc.currency}}));
            frm.set_query('cost_center',()=>({filters:{company:frm.doc.company,is_group:0}}));
            frm.set_query('batch_no','materials',(doc,cdt,cdn)=>({filters:{item:locals[cdt][cdn].item_code,disabled:0}}));
            frm.set_query('batch_no','items',(doc,cdt,cdn)=>({filters:{item:locals[cdt][cdn].item_code,disabled:0}}));
            frm.set_query('item_code','materials',itemQuery);
            frm.set_query('item_code','items',itemQuery);
            frm.set_query('main_item','items',itemQuery);
            frm.fields_dict.materials.grid.cannot_add_rows=true;
            frm.fields_dict.items.grid.cannot_add_rows=false;
        },
        async onload(frm){
            if(frm.is_new() && !frm.doc.company)await frm.set_value('company',frappe.defaults.get_user_default('Company'));
            if(frm.is_new() && frm.doc.company && !frm.doc.source_warehouse)await defaults(frm);
        },
        company:defaults,
        get_items_from_bom(frm){addProduct(frm,'BOM');},
        get_items_from_main_item(frm){addProduct(frm,'Main Item');},
        async source_warehouse(frm){
            if(frm.doc.docstatus || !(frm.doc.materials||[]).some(r=>r.item_code))return;
            for(const row of frm.doc.materials)row.warehouse=frm.doc.source_warehouse;
            await callDoc(frm,'refresh_costs');
        },
        refresh(frm){
            setupMaterialDisplay(frm);
            setupSections(frm);
            window.retail?.scrollable_grid?.enable(frm,'items',{item_code_as_title:true});
            setupRemarks(frm);
            if(frm.doc.docstatus===0){
                frm.add_custom_button(__('From BOM'),()=>addProduct(frm,'BOM'),__('Get Items'));
                frm.add_custom_button(__('From Main Item'),()=>addProduct(frm,'Main Item'),__('Get Items'));
                frm.add_custom_button(__('Refresh Stock and Costs'),()=>callDoc(frm,'refresh_costs'));
            }
            if((frm.doc.items||[]).some(r=>r.item_code))frm.add_custom_button(__('Consumption Details'),()=>consumptionDetails(frm));
            if(frm.doc.stock_entry){
                view(frm,'Stock Ledger','Stock Ledger');
                view(frm,'Accounting Ledger','General Ledger',{categorize_by:'Categorize by Voucher (Consolidated)'});
                view(frm,'Serial and Batch Summary','Serial and Batch Summary',{voucher_type:'Stock Entry',voucher_no:[frm.doc.stock_entry]});
                frm.add_custom_button(__('Stock Entry'),()=>frappe.set_route('Form','Stock Entry',frm.doc.stock_entry),__('View'));
            }
            frm.set_intro(null);
        },
        before_save(frm){if(!frm.doc.posting_time)frm.doc.posting_time=frappe.datetime.now_time();},
        remarks:setupRemarks,
    });
    function calculate(frm) {
        for(const r of frm.doc.items || []){
            const materials=(frm.doc.materials||[]).filter(m=>m.row_key===r.row_key);
            const main=materials.filter(m=>m.is_main_item || m.item_code===r.main_item);
            if(r.source_type!=='BOM'){
                const previous=main.reduce((sum,m)=>sum+flt(m.qty_per_unit),0);
                for(const m of main){
                    if(m.item_code!==r.main_item){m.item_code=r.main_item;m.unit_cost=r.main_unit_cost;m.batch_no=null;m.serial_no=null;}
                    if(previous)m.qty_per_unit=flt(m.qty_per_unit)*flt(r.main_qty_per_unit)/previous;
                }
            }
            r.main_qty=flt(r.qty)*flt(r.main_qty_per_unit);
            for(const m of materials){m.qty=flt(m.qty_per_unit)*flt(r.qty);m.amount=m.qty*flt(m.unit_cost);}
            r.product_cost=materials.length?materials.reduce((sum,m)=>sum+flt(m.amount),0):flt(r.main_qty)*flt(r.main_unit_cost);
            r.total_cost=flt(r.product_cost)+flt(r.labour_cost)+flt(r.packing_cost);
            r.unit_cost=flt(r.qty)?r.total_cost/flt(r.qty):0;
        }
        for(const field of ['product_cost','labour_cost','packing_cost','total_cost'])frm.doc[field]=(frm.doc.items||[]).reduce((sum,r)=>sum+flt(r[field]),0);
        frm.refresh_fields();
    }
    frappe.ui.form.on('Product Conversion Item',{
        items_add(frm,cdt,cdn){const row=locals[cdt][cdn];row.row_key=row.row_key||frappe.utils.get_random(12);row.source_type='Main Item';row.qty=1;row.main_qty_per_unit=1;row.main_qty=1;frm.refresh_field('items');},
        async item_code(frm,cdt,cdn){
            const row=locals[cdt][cdn];const code=row.item_code;if(!code)return;
            const {message}=await frappe.db.get_value('Item',code,['item_name','stock_uom']);
            if(row.item_code!==code)return;
            await frappe.model.set_value(cdt,cdn,{item_name:message.item_name,stock_uom:message.stock_uom});
        },
        async main_item(frm,cdt,cdn){
            const row=locals[cdt][cdn];const code=row.main_item;if(!code)return;
            const {message}=await frappe.call({method:method+'get_stock_details',args:{item_code:code,warehouse:frm.doc.source_warehouse,company:frm.doc.company}});
            if(row.main_item!==code)return;
            row.main_stock_qty=message.current_stock;row.main_unit_cost=message.stock_cost;row.main_stock_uom=message.stock_uom;
            calculate(frm);
        },
        main_qty(frm,cdt,cdn){const row=locals[cdt][cdn];if(flt(row.qty))row.main_qty_per_unit=flt(row.main_qty)/flt(row.qty);calculate(frm);},
        main_qty_per_unit:calculate,
        consumption_details(frm,cdt,cdn){consumptionDetails(frm,locals[cdt][cdn]);},
        qty(frm,cdt,cdn){const row=locals[cdt][cdn];for(const m of frm.doc.materials||[])if(m.row_key===row.row_key){m.qty=flt(m.qty_per_unit)*flt(row.qty);m.amount=m.qty*flt(m.unit_cost);}calculate(frm);},
        labour_cost:calculate,packing_cost:calculate,
        items_remove(frm){const keys=new Set(frm.doc.items.map(r=>r.row_key));frm.doc.materials=(frm.doc.materials||[]).filter(r=>keys.has(r.row_key));frm.doc.materials.forEach((r,i)=>r.idx=i+1);calculate(frm);},
    });
    frappe.ui.form.on('Product Conversion Material',{
        qty(frm,cdt,cdn){const m=locals[cdt][cdn];const r=frm.doc.items.find(r=>r.row_key===m.row_key);if(r && flt(r.qty))m.qty_per_unit=flt(m.qty)/flt(r.qty);m.amount=flt(m.qty)*flt(m.unit_cost);calculate(frm);},
        qty_per_unit(frm,cdt,cdn){const m=locals[cdt][cdn];const r=frm.doc.items.find(r=>r.row_key===m.row_key);if(r)m.qty=flt(m.qty_per_unit)*flt(r.qty);m.amount=flt(m.qty)*flt(m.unit_cost);calculate(frm);},
        materials_remove:calculate,
    });
})();

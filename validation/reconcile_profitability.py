import frappe,json
from pathlib import Path
from retail.retail_app.report.profitability import sales_cost_join,sales_cost_sql,invoice_profitability
frappe.init(site='retail-test.localhost',sites_path='/home/adler/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
result={'site':frappe.local.site,'documents':[]}
for dt in ['Sales Invoice','POS Invoice']:
 for name in frappe.get_all(dt,filters={'docstatus':1},pluck='name'):
  d=frappe.get_doc(dt,name)
  fields=['name','company','posting_date','is_return','return_against','update_stock','base_total','base_net_total','base_discount_amount','base_total_taxes_and_charges','apply_discount_on','custom_is_van_sale','consolidated_invoice']
  row={f:d.get(f) for f in fields};row['doctype']=dt
  row['items']=[{f:i.get(f) for f in ['name','item_code','qty','stock_qty','rate','base_amount','base_net_amount','discount_amount','distributed_discount_amount','pricing_rules','is_free_item','delivery_note','dn_detail','pos_invoice','pos_invoice_item','expense_account']} for i in d.items]
  row['taxes']=[{f:t.get(f) for f in ['account_head','included_in_print_rate','rate','base_tax_amount_after_discount_amount']} for t in d.taxes]
  row['sle']=frappe.db.sql('select voucher_type,voucher_no,voucher_detail_no,actual_qty,stock_value_difference from `tabStock Ledger Entry` where voucher_type=%s and voucher_no=%s and is_cancelled=0',(dt,name),as_dict=True)
  row['gl_cogs']=frappe.db.sql("select g.account,sum(g.debit-g.credit) amount from `tabGL Entry` g join `tabAccount` a on a.name=g.account where g.voucher_type=%s and g.voucher_no=%s and g.is_cancelled=0 and a.account_type='Cost of Goods Sold' group by g.account",(dt,name),as_dict=True)
  if dt=='Sales Invoice':
   row['report_costs']=frappe.db.sql(f'select sii.name,{sales_cost_sql()} cost from `tabSales Invoice` si join `tabSales Invoice Item` sii on sii.parent=si.name {sales_cost_join()} where si.name=%s',(name,),as_dict=True)
  row['gl']=frappe.db.sql('select g.account,a.account_type,g.debit,g.credit from `tabGL Entry` g join `tabAccount` a on a.name=g.account where g.voucher_type=%s and g.voucher_no=%s and g.is_cancelled=0',(dt,name),as_dict=True)
  costs={x['name']:x['cost'] for x in row.get('report_costs',[])}
  if dt=='POS Invoice':
   from retail.retail_app.report.pos_report_utils import pos_cost_joins
   costs={x['name']:x['cost'] for x in frappe.db.sql(f"select pii.name,coalesce(consolidated_cost.cost_amount,direct_cost.cost_amount) cost from `tabPOS Invoice` pi join `tabPOS Invoice Item` pii on pii.parent=pi.name {pos_cost_joins()} where pi.name=%s",(name,),as_dict=True)}
  row['profitability']=invoice_profitability(d,costs,vat_accounts={'VAT 5% - N'})
  row['item_net_matches_header']=abs(sum(i.base_net_amount for i in d.items)-d.base_net_total)<0.011
  row['stock_gl_cost']=sum(g.credit-g.debit for g in row['gl'] if g.account_type=='Stock')
  row['vat_gl']=sum(g.credit-g.debit for g in row['gl'] if g.account=='VAT 5% - N')
  result['documents'].append(row)
merge=frappe.get_doc('POS Invoice Merge Log','PIM-4')
result['pos12_merge']={'name':merge.name,'pos_closing_entry':merge.pos_closing_entry,'references':[{'pos_invoice':r.pos_invoice} for r in merge.pos_invoices]}
result['delivery_links']=frappe.db.sql('select si.name,si.is_return,sii.delivery_note,sii.dn_detail,sii.stock_qty,sii.base_net_amount from `tabSales Invoice` si join `tabSales Invoice Item` sii on sii.parent=si.name where si.docstatus=1 and coalesce(sii.delivery_note, "")!=""',as_dict=True)
result['valuation_methods']=frappe.db.sql('select distinct i.name,i.valuation_method from `tabItem` i join `tabSales Invoice Item` sii on sii.item_code=i.name join `tabSales Invoice` si on si.name=sii.parent where si.docstatus=1',as_dict=True)
result['reposts']=frappe.get_all('Repost Item Valuation',fields=['name','status','voucher_type','voucher_no'],limit=30)
result['cancelled']=frappe.get_all('Sales Invoice',filters={'docstatus':2},fields=['name','is_return','base_net_total'])
Path('/home/adler/frappe-bench/apps/retail/validation/profitability_live_evidence.json').write_text(json.dumps(result,default=str,indent=2))
print('saved',len(result['documents']),'documents; merge',result['pos12_merge'])
print('delivery links',len(result['delivery_links']))
print('reposts',len(result['reposts']))
print('cancelled',result['cancelled'])
for r in result['documents']:
 if r['doctype']=='Sales Invoice':
  cost=r['profitability']['cost_amount']
  if not r['item_net_matches_header'] or (cost is not None and abs(cost-r['stock_gl_cost'])>.011) or abs(r['profitability']['vat']-r['vat_gl'])>.011:
   print('reconciliation failure',r['name'],'net_matches',r['item_net_matches_header'],'cost',cost,'stock_gl',r['stock_gl_cost'],'VAT',r['profitability']['vat'],'VAT_GL',r['vat_gl'])
frappe.db.rollback();frappe.destroy()

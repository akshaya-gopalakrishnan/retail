"""Rollback-only verification of loyalty tender sequencing and one sync log."""
import frappe,json,copy
from unittest.mock import patch
from frappe.utils import nowdate
from retail.api import pos_sync as api
from retail import pos_offline_promotions as offline
def run_integration():
 if frappe.local.site != 'retail-test.localhost':
  raise RuntimeError('Local rollback-only verification')
 frappe.set_user('Administrator');frappe.flags.in_test=True
 try:
  token=frappe.generate_hash(length=10)
  base=frappe.parse_json(frappe.db.get_value('POS Sync Log','PSL-3067','request_json'))
  base=base.get('payload',base)
  company=frappe.get_doc('Company','nesto')
  program=frappe.get_doc(dict(doctype='Loyalty Program',loyalty_program_name='Verify '+token,loyalty_program_type='Single Tier Program',from_date=nowdate(),auto_opt_in=0,conversion_factor=1,expiry_duration=365,company=company.name,expense_account=company.default_expense_account,cost_center=company.cost_center,collection_rules=[dict(tier_name='Base',min_spent=0,collection_factor=1)])).insert()
  customer=frappe.get_doc(dict(doctype='Customer',customer_name='Verify '+token,customer_type='Individual',customer_group=frappe.db.get_value('Customer Group',{'is_group':0},'name'),territory='All Territories',loyalty_program=program.name)).insert()
  item=frappe.get_doc(dict(doctype='Item',item_code='VERIFY-'+token,item_name='Verify loyalty',item_group=frappe.db.get_value('Item Group',{'is_group':0},'name'),stock_uom='Nos',is_stock_item=0,is_sales_item=1)).insert().name
  def sale(suffix,total,payments):
   p=frappe._dict(copy.deepcopy(base))
   p.update(customer=customer.name,external_pos_reference='VERIFY-'+token+suffix,posting_date=nowdate(),business_date=nowdate(),grand_total=total,vat_amount=0,discount_amount=0,update_stock=0,payments=payments,credit_sale_amount=0,items=[dict(item_code=item,qty=1,uom=frappe.db.get_value('Item',item,'stock_uom'),conversion_factor=1,rate=total,amount=total,net_amount=total,vat_amount=0,vat_rate=0,rate_includes_vat=0)])
   for k in ('rounded_total','rounding_adjustment','issued_vouchers','loyalty_redemption'):p.pop(k,None)
   response=api.create_pos_invoice(p)
   tx=frappe.get_doc('POS Accepted Transaction',response['accepted_transaction'])
   assert tx.sales_invoice,(tx.status,tx.exception_reason)
   return p,tx,frappe.get_doc('POS Invoice',tx.pos_invoice)
  with patch.object(frappe.db,'commit',side_effect=RuntimeError('Commit forbidden')),patch.object(frappe,'enqueue'),patch.object(frappe,'publish_realtime'):
   sale('seed',100,[dict(mode_of_payment='Cash',amount=100)])
   before=frappe.db.count('POS Sync Log')
   payload,tx,doc=sale('mixed',50,[dict(mode_of_payment='Loyalty',amount=10,points=10),dict(mode_of_payment='Card',amount=10),dict(mode_of_payment='Cash',amount=10),dict(mode_of_payment='Cheque',amount=20)])
   entries=frappe.get_all('Loyalty Point Entry',filters={'invoice_type':'POS Invoice','invoice':doc.name},fields=['name','loyalty_points','purchase_amount','redeem_against','creation'],order_by='creation asc')
   print('ENTRIES',entries)
   assert [r.loyalty_points for r in entries]==[-10,40],entries
   assert entries[1].purchase_amount==40
   assert frappe.db.count('POS Sync Log')-before==1,'Extra sync log'
   offline.apply(doc)
   retry=api.create_pos_invoice(payload)
   assert retry.get('duplicate'),retry
   assert frappe.db.count('Loyalty Point Entry',{'invoice_type':'POS Invoice','invoice':doc.name})==2
   assert frappe.db.count('POS Sync Log')-before==1
   print('PASS full accounting',tx.sales_invoice,'redemption before earning, -10/+40, one log, retry unchanged')
 finally:
  frappe.db.rollback()

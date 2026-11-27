"""Database-free API boundary checks. Posting proof lives in validation/van_sales_api_isolated.py."""
import unittest
from unittest.mock import Mock, patch
import frappe
from retail.api import van_sales as api
from retail.api import pos_sync


class TestVanSalesAPI(unittest.TestCase):
    def setUp(self):
        frappe.local.flags = frappe._dict(in_test=False)

    def test_client_aliases_normalize_and_conflicting_identities_fail(self):
        p = api._payload('{"driver_id":"D","session_id":"S"}', warehouse='W')
        self.assertEqual(p, dict(driverid='D',sessionid='S',warehouse='W'))
        with patch.object(frappe,'throw',side_effect=frappe.ValidationError):
            with self.assertRaises(frappe.ValidationError):
                api._payload(driverid='D',driver_id='OTHER')
            for value in ([], '[]', '1'):
                with self.assertRaises(frappe.ValidationError):api._payload(value)

    def test_money_and_qty_cannot_be_nonfinite_or_negative(self):
        with patch.object(frappe,'throw',side_effect=frappe.ValidationError):
            for value in (None, '', 'NaN', float('inf'), -1, 0):
                with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
                    api._amount(value,'Amount')
        self.assertEqual(api._amount(0,'Amount',zero=True),0)
        self.assertEqual(api._amount('12.50','Amount'),12.5)

    def test_idempotency_is_required_before_handler_can_run(self):
        handler=Mock()
        with patch.object(api,'_require'),patch.object(frappe,'throw',side_effect=frappe.ValidationError):
            for requestid in (None,'',' '*3,'x'*141):
                with self.assertRaises(frappe.ValidationError):
                    api._post('sale',frappe._dict(requestid=requestid),handler)
        handler.assert_not_called()

    def test_invoice_discount_switching_clearing_and_validation(self):
        doc=frappe._dict(apply_discount_on='Net Total',additional_discount_percentage=10,discount_amount=12)
        api._set_invoice_discount(doc,frappe._dict())
        self.assertEqual(doc.discount_amount,12)
        api._set_invoice_discount(doc,frappe._dict(discount_amount=5))
        self.assertEqual((doc.apply_discount_on,doc.additional_discount_percentage,doc.discount_amount),('Net Total',0,5))
        api._set_invoice_discount(doc,frappe._dict(additional_discount_percentage=20))
        self.assertEqual((doc.additional_discount_percentage,doc.discount_amount),(20,0))
        api._set_invoice_discount(doc,frappe._dict(discount_amount=0))
        self.assertEqual((doc.additional_discount_percentage,doc.discount_amount),(0,0))
        fresh=frappe._dict()
        api._set_invoice_discount(fresh,frappe._dict(discount_amount=5))
        self.assertEqual(fresh.apply_discount_on,'Grand Total')
        with patch.object(frappe,'throw',side_effect=frappe.ValidationError):
            for values in (dict(discount_amount=-1),dict(discount_amount='NaN'),
                    dict(additional_discount_percentage=101),dict(apply_discount_on='Other'),
                    dict(discount_amount=1,additional_discount_percentage=10)):
                with self.subTest(values=values),self.assertRaises(frappe.ValidationError):
                    api._set_invoice_discount(doc,frappe._dict(values))

    def test_logged_driver_cannot_impersonate_request_driver(self):
        with patch.object(api,'_require'),patch.object(api,'_manager',return_value=False), \
             patch.object(frappe,'get_all',return_value=['OWN']), \
             patch.object(frappe,'get_doc') as doc,patch.object(frappe,'throw',side_effect=frappe.PermissionError):
            frappe.local.session=frappe._dict(user='driver@example.com')
            with self.assertRaises(frappe.PermissionError):api._driver(frappe._dict(driverid='OTHER'))
        doc.assert_not_called()

    def test_compatibility_methods_delegate_without_pos_authorization(self):
        for name,target in [('start_session','start_session'),('get_sales_invoices','get_sales_invoice_data'),
                ('get_sales_returns','get_sales_return_data'),('get_customer_payments','get_customer_payment_data'),
                ('get_expenses','get_expense_data')]:
            with self.subTest(name=name),patch.object(api,target,return_value={'status':'Success'}) as call, \
                 patch.object(pos_sync,'_assert_pos_user',side_effect=AssertionError('POS credentials were required')):
                self.assertEqual(getattr(pos_sync,name)(driver_id='D'),{'status':'Success'})
                call.assert_called_once_with(data=None,driver_id='D')

    def test_guest_blocked_before_module_or_data_access(self):
        frappe.local.session=frappe._dict(user='Guest')
        with patch.object(frappe,'throw',side_effect=frappe.AuthenticationError),patch.object(frappe,'get_roles') as roles:
            with self.assertRaises(frappe.AuthenticationError):api._require()
        roles.assert_not_called()

    def test_disabled_or_misconfigured_mode_cannot_post_payment(self):
        with patch.object(frappe.db,'get_value',return_value=0),patch.object(frappe,'throw',side_effect=frappe.ValidationError):
            with self.assertRaises(frappe.ValidationError):api._mode_account(frappe._dict(company='C'),'Cash')

    def test_payment_requires_references_and_exact_allocation(self):
        ctx=frappe._dict(company='C',currency='AED')
        with patch.object(api,'_customer'),patch.object(api,'_mode_account',return_value='Cash'), \
             patch.object(frappe,'throw',side_effect=frappe.ValidationError), \
             patch('erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry') as build:
            with self.assertRaises(frappe.ValidationError):api._make_payment(ctx,'CU','Cash',10,[],None)
        build.assert_not_called()


class TestHistoricalVanCollections(unittest.TestCase):
    def test_later_session_can_collect_same_driver_invoice_but_cannot_cross_assignments(self):
        from retail import van_payment
        doc=frappe._dict(custom_van_session='TODAY',custom_driver='D',company='C',references=[
            frappe._dict(reference_doctype='Sales Invoice',reference_name='OLD-INVOICE',idx=1)])
        frappe.local.session=frappe._dict(user='driver@example.com')
        for invoice_driver,company,owner,allowed in [('D','C','driver@example.com',True),
                ('OTHER','C','driver@example.com',False),('D','OTHER','driver@example.com',False),
                ('D','C','other@example.com',False)]:
            invoice=frappe._dict(custom_is_van_sale=1,custom_van_session='PREVIOUS',custom_driver=invoice_driver,company=company)
            with self.subTest(driver=invoice_driver,company=company,owner=owner), \
                 patch('retail.van_assignment.is_operator',return_value=True), \
                 patch.object(van_payment,'_',side_effect=lambda text:text), \
                 patch.object(frappe.db,'get_value',side_effect=[invoice,owner]), \
                 patch.object(frappe,'throw',side_effect=frappe.ValidationError):
                if allowed:van_payment.validate_van_payment_references(doc)
                else:
                    with self.assertRaises(frappe.ValidationError):van_payment.validate_van_payment_references(doc)


class TestVanHTTPModuleGate(unittest.TestCase):
    def test_van_aliases_use_van_gate_and_original_pos_routes_keep_pos_gate(self):
        from types import SimpleNamespace
        from retail import module_access
        routes=[('retail.api.pos_sync.get_expenses','Van Sales'),
            ('retail.api.pos_sync.start_session','Van Sales'),
            ('retail.api.van_sales.get_van_master_data','Van Sales'),
            ('retail.api.pos_sync.get_pos_master_data','POS'),
            ('retail.api.pos_sync.upsert_customer','POS')]
        previous=getattr(frappe.local,'request',None)
        try:
            for command,expected in routes:
                frappe.local.form_dict=frappe._dict()
                frappe.local.request=SimpleNamespace(path='/api/method/'+command)
                with self.subTest(command=command),patch.object(module_access,'require') as require:
                    module_access.guard_request()
                    require.assert_called_once_with(expected)
            for command in ('retail.api.pos_sync.driver_login','retail.api.van_sales.driver_login'):
                frappe.local.request=SimpleNamespace(path='/api/method/'+command)
                with patch.object(module_access,'require') as require:
                    module_access.guard_request()
                    require.assert_not_called()  # Public login performs native auth + post-login gate itself.
        finally:
            frappe.local.request=previous


class TestVanReassignment(unittest.TestCase):
    def test_closed_historical_session_does_not_grant_current_stock_after_reassignment(self):
        frappe.local.session=frappe._dict(user='old-driver@example.com')
        driver=frappe._dict(name='OLD-DRIVER')
        session=frappe._dict(name='OLD-SESSION',van='VAN',van_warehouse='WH',status='Closed',docstatus=1,check_permission=lambda _:None)
        van=frappe._dict(name='VAN',default_driver='NEW-DRIVER',vehicle_status='Active',van_warehouse='WH',check_permission=lambda _:None)
        with patch.object(api,'_driver',return_value=driver),patch.object(api,'_manager',return_value=False), \
             patch.object(frappe,'get_all',return_value=['OLD-SESSION']), \
             patch.object(frappe,'get_doc',side_effect=[session,van]), \
             patch.object(frappe.db,'get_value') as data, \
             patch.object(frappe,'throw',side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):api._context(frappe._dict(sessionid='OLD-SESSION'))
        data.assert_not_called()

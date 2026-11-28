import unittest
from unittest.mock import patch

import frappe
from retail.core_compat.runtime import _install_error_response_guard


class TestErrorResponseGuard(unittest.TestCase):
    def test_closed_console_preserves_request_error_and_install_is_idempotent(self):
        errors = []
        def disconnected(message):
            raise BrokenPipeError(32, 'Broken pipe')
        with patch.object(frappe, 'errprint', disconnected), patch.object(frappe, 'error_log', errors):
            _install_error_response_guard()
            wrapped = frappe.errprint
            _install_error_response_guard()
            self.assertIs(frappe.errprint, wrapped)
            frappe.errprint('Valuation Rate Missing')
        self.assertEqual(errors, [{'exc': 'Valuation Rate Missing'}])

    def test_healthy_console_delegates_and_other_errors_are_not_hidden(self):
        with patch.object(frappe, 'errprint', return_value=None) as original:
            _install_error_response_guard()
            frappe.errprint('test')
            original.assert_called_once_with('test')
        with patch.object(frappe, 'errprint', side_effect=ValueError('unexpected')):
            _install_error_response_guard()
            with self.assertRaises(ValueError):
                frappe.errprint('test')

"""Batch creation defaults owned by Retail; existing valuation flags stay intact."""

from frappe.utils import cint
from erpnext.stock.doctype.batch.batch import Batch


class RetailBatch(Batch):
	def set_batchwise_valuation(self):
		if self.is_new() and not cint(self.use_batchwise_valuation):
			self.use_batchwise_valuation = 0
			return
		# Preserve ERPNext's Stock Settings restriction for an explicit opt-in.
		super().set_batchwise_valuation()

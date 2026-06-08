from __future__ import annotations

import frappe
from frappe.model.document import Document


class CRMLeadAssignmentRule(Document):
	def validate(self) -> None:
		if self.priority is None:
			self.priority = 100
		if not self.strategy:
			self.strategy = "Balanced Load"
		if self.metadata_filters_json:
			try:
				frappe.parse_json(self.metadata_filters_json)
			except Exception:
				frappe.throw("Metadata Filters JSON must be valid JSON.")


from __future__ import annotations

import frappe


def after_install() -> None:
	after_migrate()


def after_migrate() -> None:
	from crm_lead_assignment.patches.v1_0.ensure_indexes import execute

	execute()
	try:
		from crm_lead_assignment.engine.counters import sync_from_teams

		sync_from_teams()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "CRM Lead Assignment Agent State Sync Failed")

	if frappe.db.exists("DocType", "CRM Lead Assignment Settings"):
		settings = frappe.get_single("CRM Lead Assignment Settings")
		if not settings.enabled:
			settings.enabled = 1
		settings.save(ignore_permissions=True)

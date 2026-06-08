from __future__ import annotations

import frappe

from crm_lead_assignment.engine.queue import enqueue_lead
from crm_lead_assignment.engine.service import can_auto_assign_lead
from crm_lead_assignment.engine.sync import sync_assignment_helpers
from crm_lead_assignment.settings import get_settings

WATCH_FIELDS = {
	"status",
	"source",
	"sr_lead_pipeline",
	"sr_lead_disposition",
	"disposition",
	"campaign",
	"utm_campaign",
	"sr_campaign",
	"sr_utm_campaign",
	"sr_utm_campaign_id",
	"sr_f_campaign_id",
	"sr_f_campaign_name",
	"sr_w_campaign_name",
	"sr_w_source_id",
	"lead_score",
	"lead_temperature",
}


def before_validate(doc, method: str | None = None) -> None:
	if getattr(frappe.flags, "crm_lead_assignment_disable_hooks", False):
		return

	settings = get_settings()
	if not settings.enabled or not doc.is_new():
		return

	if doc.get("lead_owner"):
		doc.set("lead_owner", None)
		if hasattr(doc, "team"):
			doc.set("team", None)


def after_insert(doc, method: str | None = None) -> None:
	if getattr(frappe.flags, "crm_lead_assignment_disable_hooks", False):
		return

	settings = get_settings()
	if not settings.enabled:
		return

	if doc.get("lead_owner"):
		sync_assignment_helpers(doc.name, doc.get("lead_owner"), team=doc.get("team"))
		return

	if settings.auto_assign_on_insert:
		if not can_auto_assign_lead(doc.name, event_type="Insert"):
			return
		enqueue_lead(doc.name, event_type="Insert", process_now=True)


def on_update(doc, method: str | None = None) -> None:
	if getattr(frappe.flags, "crm_lead_assignment_disable_hooks", False):
		return

	settings = get_settings()
	if not settings.enabled or getattr(frappe.flags, "crm_lead_assignment_in_progress", False):
		return

	if doc.has_value_changed("lead_owner"):
		sync_assignment_helpers(doc.name, doc.get("lead_owner"), team=doc.get("team"))
		return

	if not settings.auto_reassign_on_update:
		return

	if any(_has_changed(doc, fieldname) for fieldname in WATCH_FIELDS):
		if not can_auto_assign_lead(doc.name, event_type="Update"):
			return
		enqueue_lead(doc.name, event_type="Update", process_now=True)


def _has_changed(doc, fieldname: str) -> bool:
	return hasattr(doc, fieldname) and doc.has_value_changed(fieldname)

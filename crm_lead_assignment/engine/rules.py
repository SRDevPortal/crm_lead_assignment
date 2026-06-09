from __future__ import annotations

import frappe
from frappe.utils import cint

from crm_lead_assignment.engine.context import (
	get_campaign,
	get_disposition,
	get_lead_score,
	get_pipeline,
	get_source_id,
)


def match_rule(lead: dict, *, event_type: str | None = None) -> frappe._dict | None:
	rules = frappe.get_all(
		"CRM Lead Assignment Rule",
		filters={"enabled": 1},
		fields=[
			"name",
			"rule_name",
			"priority",
			"strategy",
			"team",
			"target_agents",
			"target_source",
			"pipeline",
			"source_id_values",
			"source",
			"campaign",
			"campaign_values",
			"status",
			"disposition",
			"lead_score_min",
			"lead_score_max",
			"only_if_unassigned",
			"max_open_leads_per_agent",
			"reassign_after_minutes",
			"fallback_user",
			"fallback_team",
			"metadata_filters_json",
		],
		order_by="priority asc, modified asc",
		limit_page_length=0,
	)

	for rule in rules:
		rule = frappe._dict(rule)
		if _matches_rule(rule, lead, event_type=event_type):
			return rule
	return None


def _matches_rule(rule: frappe._dict, lead: dict, *, event_type: str | None = None) -> bool:
	if cint(rule.only_if_unassigned) and lead.get("lead_owner") and event_type not in {"Reassign", "Stale"}:
		return False

	if not _matches_any(rule.pipeline, get_pipeline(lead)):
		return False
	if not _matches_any(rule.source_id_values, get_source_id(lead)):
		return False
	if not _matches_any(rule.source, lead.get("source")):
		return False
	if not _matches_any(rule.campaign_values or rule.campaign, get_campaign(lead)):
		return False
	if not _matches_any(rule.status, lead.get("status")):
		return False
	if not _matches_any(rule.disposition, get_disposition(lead)):
		return False

	score = get_lead_score(lead)
	if _has_bound(rule.lead_score_min) and (score is None or score < float(rule.lead_score_min)):
		return False
	if _has_bound(rule.lead_score_max) and (score is None or score > float(rule.lead_score_max)):
		return False

	return _matches_metadata(rule.metadata_filters_json, lead)


def _matches(expected, actual) -> bool:
	if expected in (None, ""):
		return True
	return str(expected).strip() == str(actual or "").strip()


def _has_bound(value) -> bool:
	return value not in (None, "", 0, 0.0)


def _matches_any(expected, actual) -> bool:
	values = _split_values(expected)
	if not values:
		return True
	return str(actual or "").strip() in values


def _split_values(raw) -> set[str]:
	if raw in (None, ""):
		return set()
	if isinstance(raw, list | tuple | set):
		return {str(value).strip() for value in raw if str(value).strip()}
	return {part.strip() for part in str(raw).replace(",", "\n").splitlines() if part.strip()}


def _matches_metadata(metadata_filters_json: str | None, lead: dict) -> bool:
	if not metadata_filters_json:
		return True

	filters = frappe.parse_json(metadata_filters_json)
	if not isinstance(filters, dict):
		return True

	for fieldname, expected in filters.items():
		if isinstance(expected, list | tuple | set):
			if lead.get(fieldname) not in expected:
				return False
		elif not _matches_any(expected, lead.get(fieldname)):
			return False
	return True

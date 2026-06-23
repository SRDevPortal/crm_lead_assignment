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
from crm_lead_assignment.settings import get_settings


def match_rule(lead: dict, *, event_type: str | None = None) -> frappe._dict | None:
	fields = _rule_fields(
		[
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
			"unassign_enabled",
			"unassign_condition",
		]
	)

	rules = frappe.get_all(
		"CRM Lead Assignment Rule",
		filters={"enabled": 1},
		fields=fields,
		order_by="priority asc, modified asc",
		limit_page_length=0,
	)

	for rule in rules:
		rule = frappe._dict(rule)
		if _matches_rule(rule, lead, event_type=event_type):
			return rule
	return None


def match_unassign_rule(lead: dict, *, event_type: str | None = None) -> frappe._dict | None:
	fields = _rule_fields(
		[
			"name",
			"rule_name",
			"priority",
			"strategy",
			"team",
			"target_source",
			"unassign_enabled",
			"unassign_condition",
			"metadata_filters_json",
		]
	)

	rules = frappe.get_all(
		"CRM Lead Assignment Rule",
		filters={"enabled": 1, "unassign_enabled": 1},
		fields=fields,
		order_by="priority asc, modified asc",
		limit_page_length=0,
	)

	for rule in rules:
		rule = frappe._dict(rule)
		if _matches_unassign_rule(rule, lead, event_type=event_type):
			return rule
	return None


def _rule_fields(fieldnames: list[str]) -> list[str]:
	available = []
	for fieldname in fieldnames:
		if fieldname == "name" or frappe.db.has_column("CRM Lead Assignment Rule", fieldname):
			available.append(fieldname)
	return available


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

	settings = get_settings()
	if cint(settings.enable_metadata_based_assignment):
		return matches_metadata_filters(get_metadata_filters(rule.name), lead) and _matches_metadata(
			rule.get("metadata_filters_json"), lead
		)
	return True


def _matches_unassign_rule(rule: frappe._dict, lead: dict, *, event_type: str | None = None) -> bool:
	settings = get_settings()
	matched = False

	unassign_filters = get_metadata_filters(rule.name, parentfield="unassign_metadata_filters")
	if (
		cint(settings.enable_metadata_based_assignment)
		and unassign_filters
		and matches_metadata_filters(unassign_filters, lead)
	):
		matched = True

	if rule.get("unassign_condition"):
		try:
			if frappe.safe_eval(rule.get("unassign_condition"), None, frappe._dict(lead)):
				matched = True
		except Exception as exc:
			frappe.msgprint(
				frappe._("CRM Lead unassign condition failed for rule {0}: {1}").format(
					rule.get("name"), exc
				),
				indicator="orange",
			)

	return matched


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
			if _lead_value(lead, fieldname) not in expected:
				return False
		elif not _matches_any(expected, _lead_value(lead, fieldname)):
			return False
	return True


def get_metadata_filters(
	rule_name: str | None,
	*,
	parentfield: str = "metadata_filters",
) -> list[frappe._dict]:
	if not rule_name or not frappe.db.exists("DocType", "CRM Lead Assignment Metadata Filter"):
		return []

	return frappe.get_all(
		"CRM Lead Assignment Metadata Filter",
		filters={
			"parent": rule_name,
			"parenttype": "CRM Lead Assignment Rule",
			"parentfield": parentfield,
			"enabled": 1,
		},
		fields=["fieldname", "operator", "value", "value_to"],
		order_by="idx asc",
		limit_page_length=0,
	)


def matches_metadata_filters(filters: list[dict], lead: dict) -> bool:
	for row in filters:
		if not _matches_metadata_filter(frappe._dict(row), lead):
			return False
	return True


def _matches_metadata_filter(row: frappe._dict, lead: dict) -> bool:
	operator = row.operator or "Equals"
	actual = _lead_value(lead, row.fieldname)

	if operator == "Is Set":
		return actual not in (None, "")
	if operator == "Is Not Set":
		return actual in (None, "")
	if operator == "Equals":
		return _compare_text(actual, row.value)
	if operator == "Not Equals":
		return not _compare_text(actual, row.value)
	if operator == "In":
		return str(actual or "").strip() in _split_values(row.value)
	if operator == "Not In":
		return str(actual or "").strip() not in _split_values(row.value)
	if operator == "Greater Than":
		return _compare_number(actual, row.value, ">")
	if operator == "Less Than":
		return _compare_number(actual, row.value, "<")
	if operator == "Greater Than Or Equal":
		return _compare_number(actual, row.value, ">=")
	if operator == "Less Than Or Equal":
		return _compare_number(actual, row.value, "<=")
	if operator == "Between":
		return _between(actual, row.value, row.value_to)
	return _compare_text(actual, row.value)


def _lead_value(lead: dict, fieldname: str):
	if fieldname in lead:
		return lead.get(fieldname)
	lead_name = lead.get("name")
	if not lead_name:
		return None
	try:
		if frappe.db.has_column("CRM Lead", fieldname):
			return frappe.db.get_value("CRM Lead", lead_name, fieldname)
	except Exception:
		return None
	return None


def _compare_text(actual, expected) -> bool:
	return str(actual or "").strip() == str(expected or "").strip()


def _compare_number(actual, expected, operator: str) -> bool:
	try:
		left = float(actual)
		right = float(expected)
	except Exception:
		return False
	if operator == ">":
		return left > right
	if operator == "<":
		return left < right
	if operator == ">=":
		return left >= right
	if operator == "<=":
		return left <= right
	return False


def _between(actual, start, end) -> bool:
	try:
		value = float(actual)
		lower = float(start)
		upper = float(end)
	except Exception:
		return False
	if lower > upper:
		lower, upper = upper, lower
	return lower <= value <= upper

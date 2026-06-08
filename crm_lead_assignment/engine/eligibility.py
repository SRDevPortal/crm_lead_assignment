from __future__ import annotations

from datetime import datetime, time

import frappe
from frappe.utils import get_time, now_datetime

from crm_lead_assignment.engine.context import get_campaign, get_pipeline
from crm_lead_assignment.integrations.role_permissions import agent_allowed_for_pipeline


def get_candidate_agents(rule: frappe._dict | None, lead: dict, *, team: str | None = None) -> list[frappe._dict]:
	target_team = team or (rule.team if rule else None)
	conditions = ["s.active = 1", "ifnull(u.enabled, 0) = 1"]
	params = {}
	if target_team:
		conditions.append("s.team = %(team)s")
		params["team"] = target_team

	rows = frappe.db.sql(
		f"""
		select
			s.name,
			s.agent,
			s.team,
			s.weight,
			s.capacity,
			s.current_open_leads,
			s.today_assigned_count,
			s.last_assigned_at,
			s.load_score,
			s.allowed_pipelines,
			s.allowed_sources,
			s.allowed_campaigns,
			s.skill_tags,
			s.shift_start,
			s.shift_end
		from `tabCRM Lead Assignment Agent State` s
		left join `tabUser` u on u.name = s.agent
		where {" and ".join(conditions)}
		order by s.load_score asc, s.last_assigned_at asc, s.modified asc
		limit 5000
		""",
		params,
		as_dict=True,
	)

	return [frappe._dict(row) for row in rows if _is_eligible(row, rule, lead)]


def _is_eligible(row: dict, rule: frappe._dict | None, lead: dict) -> bool:
	if not _allowed_by_list((rule or {}).get("target_agents"), row.get("agent")):
		return False

	capacity = int(row.get("capacity") or 0)
	rule_cap = int((rule or {}).get("max_open_leads_per_agent") or 0)
	effective_capacity = min([value for value in (capacity, rule_cap) if value] or [0])
	if effective_capacity and int(row.get("current_open_leads") or 0) >= effective_capacity:
		return False

	pipeline = get_pipeline(lead)
	if not _allowed_by_list(row.get("allowed_pipelines"), pipeline):
		return False
	if not agent_allowed_for_pipeline(row.get("agent"), pipeline):
		return False
	if not _allowed_by_list(row.get("allowed_sources"), lead.get("source")):
		return False
	if not _allowed_by_list(row.get("allowed_campaigns"), get_campaign(lead)):
		return False
	if not _inside_shift(row.get("shift_start"), row.get("shift_end")):
		return False
	return True


def _allowed_by_list(raw: str | None, value: str | None) -> bool:
	values = _split_values(raw)
	if not values:
		return True
	if value in (None, ""):
		return False
	return str(value).strip() in values


def _split_values(raw: str | None) -> set[str]:
	if not raw:
		return set()
	return {part.strip() for part in str(raw).replace(",", "\n").splitlines() if part.strip()}


def _inside_shift(start_value, end_value) -> bool:
	if not start_value or not end_value:
		return True

	start = _to_time(start_value)
	end = _to_time(end_value)
	current = now_datetime().time()

	if not start or not end:
		return True
	if _seconds_between(start, end) < 60:
		return True
	if start <= end:
		return start <= current <= end
	return current >= start or current <= end


def _to_time(value) -> time | None:
	if isinstance(value, time):
		return value
	if isinstance(value, datetime):
		return value.time()
	try:
		return get_time(value)
	except Exception:
		return None


def _seconds_between(start: time, end: time) -> int:
	start_seconds = start.hour * 3600 + start.minute * 60 + start.second
	end_seconds = end.hour * 3600 + end.minute * 60 + end.second
	return abs(end_seconds - start_seconds)

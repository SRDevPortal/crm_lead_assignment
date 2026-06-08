from __future__ import annotations

import frappe

from crm_lead_assignment.engine.audit import log_assignment
from crm_lead_assignment.engine.context import get_lead_context, snapshot_json
from crm_lead_assignment.engine.counters import decrement_agent, increment_agent
from crm_lead_assignment.engine.eligibility import get_candidate_agents
from crm_lead_assignment.engine.rules import match_rule
from crm_lead_assignment.engine.strategies import select_agent
from crm_lead_assignment.engine.sync import clear_assignment_helpers, sync_assignment_helpers
from crm_lead_assignment.integrations.dedupe import should_skip_lead
from crm_lead_assignment.settings import get_settings


def assign_lead(
	lead: str,
	new_owner: str,
	*,
	reason: str | None = None,
	rule: str | None = None,
	strategy: str | None = None,
	queue: str | None = None,
	team: str | None = None,
	triggered_by: str | None = None,
	ignore_permissions: bool = False,
) -> dict:
	if not new_owner:
		frappe.throw("New owner is required.")
	if not frappe.db.exists("User", {"name": new_owner, "enabled": 1}):
		frappe.throw(f"Invalid or disabled user: {new_owner}")

	settings = get_settings()
	row = get_lead_context(lead, for_update=True)
	old_owner = row.get("lead_owner")
	old_team = row.get("team")

	if old_owner == new_owner:
		team = sync_assignment_helpers(lead, new_owner, team=team, description="Lead Owner")
		log_assignment(
			lead=lead,
			action="Skipped",
			old_owner=old_owner,
			new_owner=new_owner,
			team=team,
			rule=rule,
			strategy=strategy,
			queue=queue,
			triggered_by=triggered_by,
			reason=reason or "Lead already assigned to this owner",
			metadata_snapshot=snapshot_json(row),
		)
		return {"status": "skipped", "reason": "already_assigned", "owner": new_owner}

	frappe.flags.crm_lead_assignment_in_progress = True
	try:
		frappe.db.set_value("CRM Lead", lead, "lead_owner", new_owner)
		if old_owner:
			decrement_agent(old_owner, old_team)
		increment_agent(new_owner, team, reassigned=bool(old_owner))
		team = sync_assignment_helpers(lead, new_owner, team=team, description="Lead Owner")
	finally:
		frappe.flags.crm_lead_assignment_in_progress = False

	action = "Reassigned" if old_owner else "Assigned"
	log_assignment(
		lead=lead,
		action=action,
		old_owner=old_owner,
		new_owner=new_owner,
		team=team,
		rule=rule,
		strategy=strategy,
		queue=queue,
		triggered_by=triggered_by,
		reason=reason,
		metadata_snapshot=snapshot_json(row),
	)
	return {"status": "ok", "action": action, "old_owner": old_owner, "new_owner": new_owner}


def clear_lead_assignment(
	lead: str,
	*,
	reason: str | None = None,
	queue: str | None = None,
	triggered_by: str | None = None,
) -> dict:
	row = get_lead_context(lead)
	old_owner = row.get("lead_owner")
	old_team = row.get("team")

	frappe.flags.crm_lead_assignment_clear_in_progress = True
	try:
		frappe.db.set_value("CRM Lead", lead, "lead_owner", None)
		decrement_agent(old_owner, old_team)
		clear_assignment_helpers(lead)
	finally:
		frappe.flags.crm_lead_assignment_clear_in_progress = False

	log_assignment(
		lead=lead,
		action="Unassigned",
		old_owner=old_owner,
		queue=queue,
		triggered_by=triggered_by,
		reason=reason,
		metadata_snapshot=snapshot_json(row),
	)
	return {"status": "ok", "action": "Unassigned", "old_owner": old_owner}


def reassign_lead(lead: str, new_owner: str, **kwargs) -> dict:
	return assign_lead(lead, new_owner, **kwargs)


def auto_assign_lead(lead: str, *, event_type: str = "Manual", queue: str | None = None) -> dict:
	settings = get_settings()
	if not settings.enabled:
		return _skip(lead, "Assignment app disabled", event_type, queue)

	row = get_lead_context(lead, for_update=True)
	skip, reason = should_skip_lead(row)
	if skip:
		return _skip(lead, reason, event_type, queue, row=row)

	rule = match_rule(row, event_type=event_type)
	if not rule:
		if settings.fallback_user:
			return assign_lead(
				lead,
				settings.fallback_user,
				reason="No rule matched; fallback user selected",
				strategy=settings.default_strategy,
				queue=queue,
				team=settings.fallback_team,
				triggered_by=event_type,
				ignore_permissions=True,
			)
		return _skip(lead, "No assignment rule matched", event_type, queue, row=row)

	candidates = get_candidate_agents(rule, row)
	selected = select_agent(candidates, rule.strategy or settings.default_strategy, row)
	if not selected:
		fallback = rule.fallback_user or settings.fallback_user
		if fallback:
			return assign_lead(
				lead,
				fallback,
				reason=f"No eligible agent for rule {rule.name}; fallback user selected",
				rule=rule.name,
				strategy=rule.strategy,
				queue=queue,
				team=rule.fallback_team or rule.team or settings.fallback_team,
				triggered_by=event_type,
				ignore_permissions=True,
			)
		return _skip(lead, f"No eligible agent for rule {rule.name}", event_type, queue, row=row, rule=rule)

	return assign_lead(
		lead,
		selected.agent,
		reason=f"Auto assignment by rule {rule.name}",
		rule=rule.name,
		strategy=rule.strategy,
		queue=queue,
		team=selected.team or rule.team,
		triggered_by=event_type,
		ignore_permissions=True,
	)


def can_auto_assign_lead(lead: str, *, event_type: str = "Manual") -> bool:
	settings = get_settings()
	if not settings.enabled:
		return False

	row = get_lead_context(lead)
	skip, _reason = should_skip_lead(row)
	if skip:
		return False

	return bool(match_rule(row, event_type=event_type) or settings.fallback_user)


def _skip(
	lead: str,
	reason: str | None,
	event_type: str,
	queue: str | None,
	*,
	row: dict | None = None,
	rule: frappe._dict | None = None,
) -> dict:
	row = row or get_lead_context(lead)
	log_assignment(
		lead=lead,
		action="Skipped",
		old_owner=row.get("lead_owner"),
		rule=(rule or {}).get("name"),
		strategy=(rule or {}).get("strategy"),
		queue=queue,
		triggered_by=event_type,
		reason=reason,
		metadata_snapshot=snapshot_json(row),
	)
	return {"status": "skipped", "reason": reason}

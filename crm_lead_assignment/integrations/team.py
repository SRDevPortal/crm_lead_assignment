from __future__ import annotations

import frappe


def get_team_for_user(user: str | None, preferred_team: str | None = None) -> str | None:
	if not user:
		return None

	if preferred_team and frappe.db.exists(
		"Team User",
		{"parent": preferred_team, "parenttype": "Team", "user": user, "is_active": 1},
	):
		return preferred_team

	row = frappe.db.sql(
		"""
		select tu.parent
		from `tabTeam User` tu
		inner join `tabTeam` t on t.name = tu.parent
		where tu.parenttype = 'Team'
		  and tu.user = %s
		  and ifnull(tu.is_active, 1) = 1
		  and ifnull(t.is_active, 1) = 1
		order by t.modified desc
		limit 1
		""",
		user,
		as_dict=True,
	)
	return row[0].parent if row else None


def sync_lead_team(lead: str, owner: str | None, preferred_team: str | None = None) -> str | None:
	if not frappe.db.has_column("CRM Lead", "team"):
		return None

	team = get_team_for_user(owner, preferred_team) if owner else None
	frappe.db.set_value("CRM Lead", lead, "team", team, update_modified=False)

	if frappe.db.exists("DocType", "CRM Deal") and frappe.db.has_column("CRM Deal", "team"):
		frappe.db.sql(
			"""
			update `tabCRM Deal`
			set team = %s
			where lead = %s
			""",
			(team, lead),
		)
	return team


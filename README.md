# CRM Lead Assignment

High-volume CRM Lead assignment engine for Frappe CRM.

The app keeps `CRM Lead.lead_owner` as the source of truth and syncs helper
records such as ToDo, DocShare, and Team through a central assignment service.

## Customer number privacy

When Customer Number Privacy is enabled, the assignment engine keeps original
CRM Lead values available only for internal rule matching. Browser responses are
projected for restricted users, while queue errors, assignment audit text,
and exception traces are sanitized before storage. Assignment metadata
snapshots deliberately exclude mobile_no while preserving operational IDs and timestamps.


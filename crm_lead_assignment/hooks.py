app_name = "crm_lead_assignment"
app_title = "CRM Lead Assignment"
app_publisher = "SRIAAS"
app_description = "High-volume CRM Lead assignment engine"
app_email = "webdevelopersriaas@gmail.com"
app_license = "mit"

# Runtime integrations expect crm, team, and sriaas_role_permissions to be installed.
# Keep this empty because Frappe treats required_apps as install sources and tries
# to fetch local custom apps such as "team" from the remote app registry.
required_apps = []

# after_install = "crm_lead_assignment.install.after_install"
# after_migrate = "crm_lead_assignment.install.after_migrate"

# doctype_js = {
# 	"CRM Lead": "public/js/crm_lead_form.js",
# }

# doctype_list_js = {
# 	"CRM Lead": "public/js/crm_lead_list.js",
# }

# doc_events = {
# 	"CRM Lead": {
# 		"before_validate": ["crm_lead_assignment.events.crm_lead.before_validate"],
# 		"after_insert": ["crm_lead_assignment.events.crm_lead.after_insert"],
# 		"on_update": ["crm_lead_assignment.events.crm_lead.on_update"],
# 	},
# 	"ToDo": {
# 		"on_trash": ["crm_lead_assignment.events.todo.on_trash"],
# 	},
# }

# scheduler_events = {
# 	"cron": {
# 		"* * * * *": [
# 			"crm_lead_assignment.jobs.process_due_short_queue",
# 		],
# 		"*/5 * * * *": [
# 			"crm_lead_assignment.jobs.retry_failed_queue",
# 			"crm_lead_assignment.jobs.enqueue_stale_reassignment_candidates",
# 		],
# 		"0 * * * *": [
# 			"crm_lead_assignment.jobs.repair_agent_state_sample",
# 		],
# 		"30 2 * * *": [
# 			"crm_lead_assignment.jobs.rebuild_agent_states",
# 			"crm_lead_assignment.jobs.repair_assignment_helpers",
# 		],
# 	}
# }

# override_whitelisted_methods = {
# 	"frappe.desk.form.assign_to.add": "crm_lead_assignment.api.assign_guard.add",
# 	"frappe.desk.form.assign_to.remove": "crm_lead_assignment.api.assign_guard.remove",
# 	"frappe.desk.form.assign_to.clear": "crm_lead_assignment.api.assign_guard.clear",
# }

# fixtures = [
# 	{"dt": "Custom Field", "filters": [["module", "=", "CRM Lead Assignment"]]},
# 	{"dt": "Property Setter", "filters": [["module", "=", "CRM Lead Assignment"]]},
# ]

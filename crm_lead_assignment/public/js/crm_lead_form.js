frappe.ui.form.on("CRM Lead", {
	refresh(frm) {
		frappe.call({
			method: "crm_lead_assignment.api.context.get_crm_lead_assignment_context",
			callback(r) {
				const context = r.message || {};
				if (context.enabled && context.disable_manual_assign_to) {
					frm.page.disable_assign_to = true;
				}
			},
		});
	},
});


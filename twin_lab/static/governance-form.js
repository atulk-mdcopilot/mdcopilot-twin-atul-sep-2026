import {node} from "/snapshot.js";
import {field, codeField, checkField, makeForm, wireMutation} from "/planning-ui.js";

const roleLabels = {
  "OWN-PROJ": "Project sponsor", "OWN-CLIN": "Clinical lead", "OWN-ENG": "Engineering custodian",
  "OWN-DATA": "Data custodian", "OWN-PRIV": "Privacy reviewer", "OWN-QA": "Verification owner",
};
const retentionLabels = {
  response_days: "Maximum days after original submission", after_close_days: "Maximum days after pilot closure",
  withdrawal_days: "Maximum days after verified withdrawal", export_days: "Maximum export age (days)",
  backup_days: "Maximum backup age (days)", backup_after_deletion_days: "Maximum backup days after active deletion",
  permission_after_close_days: "Permission receipt days after pilot closure", audit_after_close_days: "Audit receipt days after pilot closure",
};
const controlLabels = {
  storage_access_verified: "Local storage and authorized device access verified",
  device_encryption_verified: "Device encryption verified on this machine",
  no_network_verified: "No external transmission verified",
  lifecycle_verified: "Expiry, withdrawal, and disposal workflow tested",
  backup_restore_verified: "Backup restoration and deletion-ledger handling tested",
  external_copy_control_verified: "Export and backup copy inventory procedures verified",
};

function section(parent, title) {
  const details = node("details", undefined, "governance-details");
  details.append(node("summary", title));
  parent.append(details);
  return details;
}

export function governanceForm(current, onSaved, onReload, reference) {
  const old = current || {};
  const approved = reference?.document_status === "approved" ? reference : null;
  const defaults = !current && approved ? {
    version: approved.retention.policy_version,
    response_days: approved.retention["RET-DEMO"].max_days_from_anchor,
    after_close_days: approved.retention["RET-DEMO"].max_days_after_pilot_close,
    withdrawal_days: approved.withdrawal.max_days_to_active_deletion_after_verification,
    export_days: approved.retention["RET-EXP"].max_days_from_creation,
    backup_days: approved.retention["RET-BAK"].max_snapshot_age_days,
    backup_after_deletion_days: approved.retention["RET-BAK"].max_additional_days_after_active_deletion,
  } : {};
  const periods = old.retention || defaults;
  const ui = makeForm("Local operating record", "The governing documents are approved. Complete the installation-specific details and evidence here; save an incomplete draft if needed. Existing records are preserved. Contacts and role acceptances stay in the private local database, outside Git.", "Save operating record");
  field(ui.fields, "title", "Policy title", "text", old.title || "", {required: true, maxLength: 200});
  field(ui.fields, "status", "Operating readiness of this revision", "select", "draft", {required: true, choices: [["draft", "Incomplete operating record — participation disabled"], ["approved", "Operating record approved — details and checks complete"], ["revoked", "Revoked — physician participation stays disabled"]]});
  const operator = section(ui.fields, "Operator and pilot dates");
  for (const [key, label] of [["legal_name", "Legal operator name"], ["project_contact", "Participant / project contact"], ["privacy_contact", "Privacy contact"], ["pilot_close_date", "Planned pilot close date"]]) {
    field(operator, `operator.${key}`, label, key === "pilot_close_date" ? "date" : "text", old.operator?.[key] || "", {maxLength: 1000});
  }
  const permission = section(ui.fields, "Exact participant permission notice");
  field(permission, "permission.version", "Notice version", "text", old.permission?.version ?? approved?.permission.document_version ?? "", {maxLength: 128});
  field(permission, "permission.text", "Complete notice shown before participation", "textarea", old.permission?.text || "", {maxLength: 20000, rows: 10, help: "Use the approved template, completing actual operator contacts, assigned session and verified practices. Document approval is separate from participant agreement. Whitespace is preserved exactly."});
  const retention = section(ui.fields, "Retention decisions — approved policy values");
  retention.append(node("p", "Response expiry uses the earlier of original submission plus the response period or pilot closure plus its period. Corrections, exports, policy revisions, and restoration do not restart that clock. Disposal is a separate authorized local operation.", "small muted"));
  field(retention, "retention.version", "Retention policy version", "text", periods.version || "", {maxLength: 128});
  for (const [key, label] of Object.entries(retentionLabels)) field(retention, `retention.${key}`, label, "number", periods[key], {min: 1, max: 3650, step: 1, help: key === "permission_after_close_days" || key === "audit_after_close_days" ? "Approved policy: one calendar year after pilot closure. Record the matching day count once that date is set; it is not always 365 days." : "New records start with the approved document's day values. Existing saved values are preserved."});
  const owners = section(ui.fields, "Accepted responsibilities — private local records");
  owners.append(node("p", "Record an actual person's acceptance for each role. A role code alone is not an appointment or login. One person may accept multiple roles; do not infer acceptance.", "small muted"));
  for (const [role, label] of Object.entries(roleLabels)) {
    const entry = old.owners?.find(item => item.role_code === role) || {};
    const group = section(owners, `${label} · ${role}`);
    codeField(group, `${role}.actor_code`, "Accepted actor code", entry.actor_code || "", false);
    field(group, `${role}.person_name`, "Accepted person's name", "text", entry.person_name || "", {maxLength: 200});
    field(group, `${role}.contact`, "Private contact", "text", entry.contact || "", {maxLength: 1000});
    field(group, `${role}.accepted_at`, "Acceptance timestamp, with timezone", "text", entry.accepted_at || "", {maxLength: 64, help: "Record the actual time of acceptance in ISO format, for example YYYY-MM-DDTHH:MM:SSZ. Blank means unaccepted."});
  }
  const controls = section(ui.fields, "Verification evidence for this revision");
  controls.append(node("p", "Checks begin unchecked for every new revision. Mark only work actually verified on this installation, and record reproducible evidence. Saving a check is an attestation, not an automated test or authentication.", "small muted"));
  codeField(controls, "controls.actor_code", "Verification actor code", "", false);
  field(controls, "controls.checked_at", "Verification timestamp, with timezone", "text", "", {maxLength: 64, help: "Use the actual verification time. This field does not fill itself."});
  field(controls, "controls.evidence", "Verification evidence and limitations", "textarea", "", {maxLength: 5000, rows: 5});
  const checks = {};
  for (const [key, label] of Object.entries(controlLabels)) checks[key] = checkField(controls, key, label);
  const approval = section(ui.fields, "Approval / revocation record");
  codeField(approval, "approved_by_code", "Reviewing actor code", "", false);
  field(approval, "approval_note", "Review determination and decision", "textarea", "", {maxLength: 5000, help: "Approval requires the accepted privacy reviewer's code, a documented review determination as applicable, accepted responsibilities, complete policy values, and all required verification evidence. Do not enter a sample approval."});
  const editor = wireMutation(ui, "/api/governance", () => {
    const values = Object.fromEntries(new FormData(ui.form));
    const group = prefix => Object.fromEntries(Object.entries(values).filter(([key]) => key.startsWith(`${prefix}.`)).map(([key, value]) => [key.slice(prefix.length + 1), value]));
    const periods = group("retention");
    for (const key of Object.keys(retentionLabels)) periods[key] = periods[key] === "" ? null : Number(periods[key]);
    return {based_on_governance_id: old.governance_id || null, title: values.title, status: values.status,
      operator: group("operator"), permission: group("permission"), retention: periods,
      owners: Object.keys(roleLabels).map(role_code => ({role_code, ...group(role_code)})),
      controls: {...group("controls"), ...Object.fromEntries(Object.entries(checks).map(([key, input]) => [key, input.checked]))},
      approved_by_code: values.approved_by_code, approval_note: values.approval_note};
  }, onSaved, onReload);
  return {panel: ui.panel, editor};
}

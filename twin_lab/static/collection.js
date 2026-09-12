import {request} from "/api.js";
import {node} from "/snapshot.js";
import {button, field, codeField, makeForm, wireMutation, mayDiscard, jsonDetails, versionChoices, heading} from "/planning-ui.js";

const labels = {
  owner_code: "Collection owner code", physician_codes: "Allowed physician codes",
  consent_statement: "Draft permission planning text", consent_version: "Planning text version",
  retention_days: "Response retention (days)", backup_owner_code: "Backup owner code",
  backup_frequency: "Backup frequency", backup_retention_days: "Backup retention (days)",
  case_assignments: "At least one version-pinned demo assignment",
};

export function initCollection(container, {onOpenAssignment}) {
  let collection = null;
  let catalog = null;
  let editors = [];
  let status = null;
  let loading = false;

  async function refresh(force = false) {
    if (loading || (force && !mayDiscard(editors))) return;
    loading = true;
    if (status) { status.textContent = "Loading local collection planning records…"; status.classList.remove("error"); }
    try {
      [collection, catalog] = await Promise.all([request("/api/collection"), request("/api/catalog")]);
      if (!force && editors.some(editor => editor.protectedDraft())) {
        status.textContent = "Saved records were refreshed. Your current form is retained; use Refresh to discard it and display the latest records.";
      } else render();
    } catch (error) {
      if (!status) status = heading(container, "LOCAL GOVERNANCE DRAFT", "Collection plan", "Define local demo rules and preserve a history of changes.", () => refresh(true));
      status.textContent = `Could not load the collection plan: ${error.message} Use Refresh to retry.`;
      status.classList.add("error");
    } finally { loading = false; }
  }

  async function saved() {
    await refresh();
    if (status) status.textContent = `Save confirmed. ${status.textContent}`;
  }

  function protocolForm() {
    const current = collection.current || {};
    const ui = makeForm("Save collection rules", "Record assignment planning decisions. Unknown fields can remain blank in an incomplete draft. This legacy plan does not approve participant permission or enforce retention. Use Governance for accepted policy and verification. Saving preserves all earlier protocol versions.", "Save protocol revision");
    field(ui.fields, "title", "Plan title", "text", current.title || "", {required: true, maxLength: 200});
    codeField(ui.fields, "owner_code", labels.owner_code, current.owner_code || "", false);
    field(ui.fields, "physician_codes", labels.physician_codes, "textarea", (current.physician_codes || []).join("\n"), {maxLength: 8200, help: "Up to 200 unique codes, one per line or separated by commas. Keep any code-to-person mapping outside Twin Lab and Git."});
    field(ui.fields, "consent_statement", labels.consent_statement, "textarea", current.consent_statement || "", {maxLength: 12000, rows: 5, help: "Planning reference only. Exact text is preserved. A saved plan is not approval or a participant's permission receipt."});
    field(ui.fields, "consent_version", labels.consent_version, "text", current.consent_version || "", {maxLength: 128});
    field(ui.fields, "retention_days", labels.retention_days, "number", current.retention_days, {min: 1, max: 3650, step: 1, help: "Enter the approved period (1–3650 days). Blank means undecided; there is no automatic deletion."});
    codeField(ui.fields, "backup_owner_code", labels.backup_owner_code, current.backup_owner_code || "", false);
    field(ui.fields, "backup_frequency", "Proposed backup frequency", "select", current.backup_frequency || "manual_before_changes", {required: true, choices: [["manual_before_changes", "Manual, before changes"], ["daily_when_collecting", "Daily when collecting"], ["weekly_when_collecting", "Weekly when collecting"]], help: "The initial manual frequency is a proposal. Confirm or replace it with the owner’s plan. No automatic backup scheduler is installed."});
    field(ui.fields, "backup_retention_days", labels.backup_retention_days, "number", current.backup_retention_days, {min: 1, max: 3650, step: 1, help: "1–3650 days. The owner must handle backup retention; no files are deleted automatically."});
    field(ui.fields, "notes", "Plan notes", "textarea", current.notes || "", {maxLength: 5000, help: "Assignment rationale, local operating procedures, and unresolved decisions. No names, credentials, or patient information."});
    ui.fields.append(node("p", "Assignment strategy: manual selection pinned to an exact case version. Purpose: demo. Study collection: disabled.", "planning-review-state"));
    editors.push(wireMutation(ui, "/api/protocols", () => {
      const values = Object.fromEntries(new FormData(ui.form));
      const codes = values.physician_codes.split(/[\s,]+/).filter(Boolean);
      if (codes.length > 200) throw new Error("Use no more than 200 allowed physician codes.");
      if (codes.some(code => !/^[A-Za-z0-9_-]{1,40}$/.test(code))) throw new Error("Each physician code must use 1–40 letters, numbers, underscores, or hyphens.");
      if (new Set(codes).size !== codes.length) throw new Error("Each allowed physician code must appear only once.");
      return {...values, based_on_protocol_id: current.protocol_id || null, physician_codes: codes,
        retention_days: values.retention_days === "" ? null : Number(values.retention_days),
        backup_retention_days: values.backup_retention_days === "" ? null : Number(values.backup_retention_days)};
    }, saved, () => refresh(true)));
    return ui.panel;
  }

  function readinessPanel() {
    const panel = node("article", undefined, "panel planning-card");
    panel.append(node("h2", "Collection planning completeness"), node("p", "Study collection is disabled, including when all planning fields are complete. Actual physician demo participation requires separate Governance readiness and an explicit permission receipt. A saved plan does not provide either.", "planning-review-state"));
    if (!collection.current) panel.append(node("p", "No collection plan has been saved. Start with a draft and record the remaining decisions.", "planning-empty"));
    const readiness = collection.readiness;
    panel.append(node("h3", readiness.missing_fields.length ? "Incomplete planning fields" : "Planning fields recorded"));
    if (readiness.missing_fields.length) {
      const missing = node("ul", undefined, "planning-list");
      readiness.missing_fields.forEach(key => missing.append(node("li", labels[key] || key.replaceAll("_", " "))));
      panel.append(missing);
    } else panel.append(node("p", "All required planning values are recorded. They have not been independently verified by this app.", "small muted"));
    if (readiness.unapproved_assignment_ids.length) {
      panel.append(node("h3", "Assignments without an approved exact case version"));
      const assignments = node("ul", undefined, "planning-list");
      readiness.unapproved_assignment_ids.forEach(id => {
        const assignment = collection.assignments.find(item => item.assignment_id === id);
        assignments.append(node("li", assignment ? `${assignment.physician_code} · ${id}` : id));
      });
      panel.append(assignments);
    }
    panel.append(node("h3", "Local collection boundaries"));
    const rules = node("ul", undefined, "planning-list");
    for (const text of ["Use coded identifiers. Store any identity mapping separately and securely.", "Assignments preserve the selected protocol and case version; they are demo plans, not enrollment or randomization.", "Obtain consent and any required institutional authorization outside this application before future study activity.", "Response and backup retention are the named owners’ responsibilities. The saved periods do not trigger deletion."]) rules.append(node("li", text));
    panel.append(rules);
    return panel;
  }

  function assignmentForm() {
    const ui = makeForm("Plan a demo assignment", "Use the current saved protocol, an allowed physician code, and the exact case version. Saved assignments remain pinned when a protocol or case changes.", "Save demo assignment");
    const protocols = collection.current ? [collection.current] : [];
    const selected = collection.current?.protocol_id || "";
    const protocol = field(ui.fields, "protocol_id", "Saved protocol", "select", selected, {required: true, choices: [["", "Select a saved protocol"], ...protocols.map(item => [item.protocol_id, `${item.title} · ${item.created_at}`])]});
    const physician = field(ui.fields, "physician_code", "Allowed physician code", "select", "", {required: true});
    const fillCodes = () => {
      const prior = physician.value;
      const codes = protocols.find(item => item.protocol_id === protocol.value)?.physician_codes || [];
      physician.replaceChildren();
      for (const code of ["", ...codes]) {
        const option = node("option", code || "Select an allowed code");
        option.value = code;
        physician.append(option);
      }
      if (codes.includes(prior)) physician.value = prior;
    };
    fillCodes();
    protocol.addEventListener("change", fillCodes);
    field(ui.fields, "version_id", "Exact case version", "select", "", {required: true, choices: [["", "Select a case version"], ...versionChoices(catalog.versions)]});
    field(ui.fields, "notes", "Assignment notes", "textarea", "", {maxLength: 5000});
    if (!protocols.length) ui.fields.append(node("p", "Save a protocol with at least one allowed physician code first.", "small muted"));
    editors.push(wireMutation(ui, "/api/assignments", () => Object.fromEntries(new FormData(ui.form)), saved, () => refresh(true)));
    return ui.panel;
  }

  function savedAssignments() {
    const panel = node("article", undefined, "panel planning-card");
    panel.append(node("h2", "Version-pinned demo assignments"));
    if (!collection.assignments.length) panel.append(node("p", "No assignments have been saved.", "planning-empty"));
    for (const assignment of collection.assignments) {
      const version = catalog.versions.find(item => item.version_id === assignment.version_id);
      const protocol = collection.history.find(item => item.protocol_id === assignment.protocol_id);
      const record = node("div", undefined, "planning-record");
      record.append(node("h3", `${assignment.physician_code} · ${version?.snapshot.title || assignment.version_id} · v${version?.case_version || "unknown"}`));
      record.append(node("p", `Protocol: ${protocol?.title || assignment.protocol_id} · Assigned ${assignment.created_at}`, "small muted"));
      record.append(node("p", assignment.notes), button("Open assigned demo response", () => onOpenAssignment(assignment.assignment_id)), jsonDetails("Exact assignment record", assignment));
      panel.append(record);
    }
    return panel;
  }

  function backupPanel() {
    const ui = makeForm("Verified local backups", "Create a consistent SQLite backup in the external data directory. The server checks its integrity before reporting success. These files share this machine’s risks; follow the documented offline restore procedure to test a separate copy.", "Create local backup");
    editors.push(wireMutation(ui, "/api/backups", () => ({}), saved, () => refresh(true)));
    if (!collection.backups.length) ui.panel.append(node("p", "No application backups have been recorded.", "planning-empty"));
    for (const backup of collection.backups) {
      const record = node("div", undefined, "planning-record");
      record.append(node("h3", backup.filename), node("p", `${backup.created_at} · ${backup.size_bytes.toLocaleString()} bytes`, "small muted"));
      record.append(node("p", `SHA-256 ${backup.sha256}`, "identifier"));
      ui.panel.append(record);
    }
    return ui.panel;
  }

  function historyPanel() {
    const panel = node("article", undefined, "panel planning-card");
    panel.append(node("h2", "Preserved protocol history"));
    if (!collection.history.length) panel.append(node("p", "No protocol versions have been saved.", "planning-empty"));
    for (const protocol of collection.history) panel.append(jsonDetails(`${protocol.title} · ${protocol.created_at}${protocol.protocol_id === collection.current?.protocol_id ? " · Current" : ""}`, protocol));
    return panel;
  }

  function render() {
    editors = [];
    container.replaceChildren();
    status = heading(container, "LOCAL GOVERNANCE DRAFT", "Collection plan", "Record collection rules, pin demo assignments, and create local backups. Earlier plans remain preserved. Study collection stays disabled.", () => refresh(true));
    const stack = node("div", undefined, "planning-stack");
    const top = node("div", undefined, "planning-columns");
    top.append(protocolForm(), readinessPanel());
    const middle = node("div", undefined, "planning-columns");
    middle.append(assignmentForm(), savedAssignments());
    stack.append(top, middle, backupPanel(), historyPanel());
    container.append(stack);
  }

  window.addEventListener("beforeunload", event => {
    if (editors.some(editor => editor.protectedDraft())) { event.preventDefault(); event.returnValue = ""; }
  });
  return refresh;
}

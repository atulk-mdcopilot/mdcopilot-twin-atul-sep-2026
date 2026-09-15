import {node} from "/snapshot.js";
import {field, codeField, makeForm, wireMutation, jsonDetails} from "/planning-ui.js";

export function renderLifecycle(data, editors, onSaved, onReload) {
  const stack = node("div", undefined, "planning-stack");
  const overview = node("article", undefined, "panel planning-card");
  overview.append(node("h2", "Response lifecycle"), node("p", "Restrictions stop ordinary review, export, and further capture. Expiry does not erase data automatically. Authorized disposal uses the documented offline preview and confirmation workflow, including controlled exports and backups.", "planning-review-state"));
  if (!data.records.length) overview.append(node("p", "No response chains are recorded.", "planning-empty"));
  for (const record of data.records) {
    const row = node("div", undefined, "planning-record");
    row.append(node("h3", `Response chain ${record.root_response_id}`));
    row.append(node("p", `Permission: ${record.permission_status || "Unknown — not established"} · ${record.ordinary_use_allowed ? "Available for ordinary review" : "Restricted from ordinary use"}`));
    row.append(node("p", `Original retention anchor: ${record.retention_anchor_at || "Not established"}\nExpiry: ${record.expires_at || "Unknown — no policy assigned"}\nRestriction: ${record.restriction || "None recorded"}`, "small muted"));
    row.append(jsonDetails("Linked records and current restrictions", record));
    overview.append(row);
  }
  overview.append(node("p", "Legacy records are not relabelled as fabricated, consented, or study data. Preserve their original provenance until a separate, documented review establishes their status.", "small muted"));
  stack.append(overview);
  const withdrawal = makeForm("Record a withdrawal request", "Use this only for an actual request. Recording receipt immediately stops further capture and ordinary use for the code, pending reasonable verification. A code alone does not verify the person. Verification and disposal follow the documented local procedure.", "Record request and stop use");
  codeField(withdrawal.fields, "physician_code", "Requesting physician code");
  codeField(withdrawal.fields, "actor_code", "Receiving operator code");
  editors.push(wireMutation(withdrawal, "/api/withdrawals", () => Object.fromEntries(new FormData(withdrawal.form)), onSaved, onReload));
  stack.append(withdrawal.panel);
  const holds = makeForm("Record a scoped hold", "An authorized hold blocks ordinary use and prevents disposal for the listed records. Enter an actual authority record and scope; this is not a general reason to retain all responses.", "Record scoped hold");
  codeField(holds.fields, "actor_code", "Recording operator code");
  field(holds.fields, "response_ids", "Affected response IDs", "textarea", "", {required: true, help: "UUIDs from the response-chain records, separated by spaces, commas, or new lines."});
  field(holds.fields, "authority_record", "Authority and documented reason", "textarea", "", {required: true, maxLength: 1000, help: "Use a minimal authority reference. Do not copy response text or patient information."});
  editors.push(wireMutation(holds, "/api/holds", () => {
    const values = Object.fromEntries(new FormData(holds.form));
    const response_ids = String(values.response_ids).split(/[\s,]+/).filter(Boolean);
    if (!response_ids.length || new Set(response_ids).size !== response_ids.length) throw new Error("Enter each affected response ID once.");
    return {...values, response_ids};
  }, onSaved, onReload));
  stack.append(holds.panel);
  const history = node("article", undefined, "panel planning-card");
  history.append(node("h2", "Restrictions, copies, and disposal preview"));
  for (const [label, rows] of [["Withdrawal requests", data.withdrawals], ["Withdrawal verification", data.verifications || []], ["Scoped holds and releases", data.holds], ["Managed exports", data.exports], ["Managed backups", data.backups]]) {
    history.append(node("h3", label));
    if (!rows.length) history.append(node("p", "No records.", "planning-empty"));
    for (const row of rows) history.append(jsonDetails(`${row.kind ? `${row.kind} · ` : ""}${row.withdrawal_id || row.hold_id || row.filename || row.backup_id || row.export_id}`, row));
  }
  history.append(node("p", "Downloaded, renamed, or copied files are outside automatic control. The operator must inventory and remove those copies. A local managed-copy record cannot prove external copies were erased.", "small muted"));
  history.append(jsonDetails("Current disposal eligibility — preview only", data.disposal));
  history.append(node("p", "Nothing is deleted by viewing this screen. See the repository's lifecycle instructions for withdrawal verification, hold release, disposal preview, and restore validation. Backup restoration must apply the current deletion ledger before the restored data is used.", "small muted"));
  stack.append(history);
  return stack;
}

import {request, downloadJSON} from "/api.js";
import {node} from "/snapshot.js";
import {button, heading, jsonDetails, mayDiscard} from "/planning-ui.js";
import {governanceForm} from "/governance-form.js";
import {renderLifecycle} from "/lifecycle.js";

export function initGovernance(container, onChange) {
  let editors = [];
  let status = null;
  let loading = false;

  async function refresh(force = false) {
    if (loading || (force && !mayDiscard(editors))) return;
    loading = true;
    try {
      const [governance, lifecycle] = await Promise.all([request("/api/governance"), request("/api/lifecycle")]);
      if (!force && editors.some(item => item.protectedDraft())) {
        status.textContent = "Saved records refreshed. Your draft is retained; use Refresh to replace it with the latest values.";
        return;
      }
      render(governance, lifecycle);
    } catch (error) {
      if (!status) status = heading(container, "LOCAL PARTICIPATION RULES", "Governance", "Versioned policy, permission records, and response lifecycle.", () => refresh(true));
      status.textContent = `Could not load governance: ${error.message} Use Refresh to retry.`;
      status.classList.add("error");
    } finally { loading = false; }
  }

  async function saved() {
    await refresh();
    await onChange();
  }

  function render(governance, lifecycle) {
    editors = [];
    container.replaceChildren();
    status = heading(container, "LOCAL PARTICIPATION RULES", "Governance", "Approved documents, local operating details, and individual permission records. Study collection, model training, and external services remain disabled.", () => refresh(true));
    const stack = node("div", undefined, "planning-stack");
    const reference = governance.reference_documents;
    if (reference) {
      const documents = node("article", undefined, "panel planning-card");
      const policy = reference.policy;
      documents.append(node("h2", policy.document_status === "approved" ? "Governance documents approved" : "Governance reference documents"));
      documents.append(node("p", `Revision ${policy.document_revision} · Project-user approval recorded ${policy.approval.recorded_at}`, "small muted"));
      documents.append(node("p", "The permission template and demo retention policy are approved. Operator contacts, role acceptances, pilot dates, verified controls, and each participant's permission must still be recorded."));
      const links = node("div", undefined, "planning-actions");
      for (const file of reference.files) {
        const link = node("a", file.format === "json" ? "Download approved policy JSON" : "Download approved governance document", "secondary-button");
        link.href = file.url;
        links.append(link);
      }
      documents.append(links, jsonDetails("Approved policy values and approval record", policy));
      stack.append(documents);
    }
    const ready = node("article", undefined, "panel planning-card");
    const enabled = governance.readiness.actual_physician_capture_enabled;
    ready.append(node("h2", enabled ? "Physician demo participation can be requested" : "Actual physician participation is disabled"));
    ready.append(node("p", enabled ? "Each participant still needs an explicit permission receipt and an approved, assigned case version. This is a local demo, not study authorization." : "Document approval is recorded separately above. Complete the local operating record and verified checks before physician participation. Fabricated software testing remains available with an explicit acknowledgement.", "planning-review-state"));
    if (governance.readiness.missing_fields.length) {
      ready.append(node("h3", "Unresolved requirements"));
      const gaps = node("ul", undefined, "planning-list");
      governance.readiness.missing_fields.forEach(key => gaps.append(node("li", key.replaceAll("_", " ").replaceAll(".", " → "))));
      ready.append(gaps);
    }
    ready.append(node("p", "Single-user local application: actor and physician codes are not authentication. The operator controls this device, permissions, and copies. No completed verification or role acceptance is inferred by the app.", "small muted"));
    stack.append(ready);
    if (governance.current) {
      const notice = node("article", undefined, "panel planning-card");
      notice.append(node("h2", `Current policy: ${governance.current.title}`), node("p", `${governance.current.status} · ${governance.current.created_at}`, "small muted"));
      const policy = governance.current;
      notice.append(node("h3", "Pilot and participant session"));
      notice.append(node("p", `Professional role: ${policy.operator.professional_role || "Unknown — not recorded in this version"}`));
      notice.append(node("p", `UTC pilot dates: ${policy.operator.pilot_start_date || "Unknown start"} through ${policy.operator.pilot_close_date || "Unknown close"}. Start inclusive; closes at 00:00 UTC after the close date.`, "small muted"));
      notice.append(node("p", policy.session?.description || "Session description: unknown — not recorded in this version."));
      notice.append(node("p", `Maximum distinct assigned case versions per physician: ${policy.session?.max_distinct_case_versions ?? "Unknown"}. This is not a total-response or time limit.`, "small muted"));
      notice.append(node("h3", `Exact permission notice · ${governance.current.permission.version || "No version recorded"}`));
      notice.append(node("div", governance.current.permission.text || "No notice text has been recorded.", "exact-notice"));
      notice.append(node("p", `SHA-256 ${governance.current.permission_sha256}`, "identifier"));
      notice.append(jsonDetails("Complete policy, decisions, and verification evidence", governance.current));
      stack.append(notice);
    }
    const form = governanceForm(governance.current, saved, () => refresh(true), reference?.policy);
    editors.push(form.editor);
    stack.append(form.panel);
    const permissions = node("article", undefined, "panel planning-card");
    permissions.append(node("h2", "Permission records"), node("p", "Agree and Decline record the exact notice shown. A receipt is not clinical or research approval, and does not establish permission for earlier responses.", "small muted"));
    if (!governance.receipts.length) permissions.append(node("p", "No permission choices have been recorded.", "planning-empty"));
    for (const receipt of governance.receipts) {
      const row = node("div", undefined, "planning-record");
      row.append(node("h3", `${receipt.physician_code} · ${receipt.choice}`), node("p", `${receipt.recorded_at} · Notice ${receipt.permission_version}`, "small muted"));
      row.append(button("Download exact participant copy", () => downloadJSON(receipt, `twin-lab-permission-${receipt.receipt_id}.json`)), jsonDetails("Receipt and exact notice", receipt));
      permissions.append(row);
    }
    stack.append(permissions, renderLifecycle(lifecycle, editors, saved, () => refresh(true)));
    const history = node("article", undefined, "panel planning-card");
    history.append(node("h2", "Preserved policy history"));
    if (!governance.history.length) history.append(node("p", "No policy revisions have been saved.", "planning-empty"));
    for (const item of governance.history) history.append(jsonDetails(`${item.title} · ${item.status} · ${item.created_at}`, item));
    stack.append(history);
    container.append(stack);
  }

  window.addEventListener("beforeunload", event => {
    if (editors.some(item => item.protectedDraft())) { event.preventDefault(); event.returnValue = ""; }
  });
  return refresh;
}

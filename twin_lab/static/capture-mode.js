import {request, downloadJSON} from "/api.js";
import {node} from "/snapshot.js";
import {button, field, codeField, checkField, makeForm, wireMutation} from "/planning-ui.js";

const modeLabel = value => ({fabricated_qa: "Fabricated software test", physician_demo: "Physician demo with recorded permission", legacy_unclassified: "Legacy response — origin and permission unverified"}[value] || "Origin and permission unverified");

export function initCaptureMode(container, {onOpenAssignment, onModeChange}) {
  let governance = null;
  let collection = null;
  let catalog = null;
  let correction = null;
  let permissionEditor = null;
  let refreshGeneration = 0;
  let selectedMode = "fabricated_qa";
  const title = node("h2", "Choose the kind of response");
  const mode = field(container, "capture_mode", "Capture mode", "select", selectedMode, {choices: [["fabricated_qa", "Fabricated software testing"], ["physician_demo", "Actual physician demo participation"]]});
  container.prepend(title);
  mode.options[1].disabled = true;
  const info = node("p", "Checking local participation requirements…", "small muted");
  info.setAttribute("role", "status");
  const qa = node("div");
  const ack = checkField(qa, "qa_acknowledged", "The next response will contain fabricated software-test answers, not my actual physician decisions or any patient information.");
  qa.append(node("p", "Required before each new presentation. This acknowledgement is saved with that presentation; it does not change older records.", "field-help"));
  const human = node("div");
  human.hidden = true;
  const current = node("p", "", "planning-review-state");
  current.hidden = true;
  container.append(info, qa, human, current);

  mode.addEventListener("change", () => {
    if (permissionEditor?.protectedDraft() || !onModeChange()) {
      mode.value = selectedMode;
      info.textContent = "Finish or discard the current response and permission request before changing mode.";
      return;
    }
    selectedMode = mode.value;
    correction = null;
    current.hidden = true;
    ack.checked = false;
    updateVisibility();
  });

  function updateVisibility() {
    qa.hidden = mode.value !== "fabricated_qa";
    human.hidden = mode.value !== "physician_demo";
  }

  function linkedPlanAvailable() {
    const policy = governance?.current;
    const plan = collection?.current;
    if (!policy) return false;
    if (policy.governance_schema_version === "2.0" && plan?.protocol_schema_version !== "2.0") return false;
    return plan?.protocol_schema_version !== "2.0" || plan.governance_id === policy.governance_id;
  }

  function renderHuman() {
    const previousReceipt = human.querySelector('[name="permission_receipt_id"]')?.value || "";
    const previousAssignment = human.querySelector('[name="assignment_id"]')?.value || "";
    human.replaceChildren();
    permissionEditor = null;
    if (!governance?.readiness.actual_physician_capture_enabled || !linkedPlanAvailable()) {
      return previousReceipt || previousAssignment ? " Previously selected permission and assignment are no longer available." : "";
    }
    const policy = governance.current;
    human.append(node("h3", `Participant permission · ${policy.permission.version}`));
    human.append(node("div", policy.permission.text, "exact-notice"));
    human.append(node("p", `Exact notice SHA-256 ${policy.permission_sha256}`, "identifier"));
    if (policy.governance_schema_version === "2.0") {
      human.append(node("p", `Operator professional role: ${policy.operator.professional_role}`));
      human.append(node("p", policy.session.description));
      human.append(node("p", `UTC pilot dates: ${policy.operator.pilot_start_date} through ${policy.operator.pilot_close_date}, ending at 00:00 UTC the following day. Maximum ${policy.session.max_distinct_case_versions} distinct assigned case versions across plans using this policy. Repeat responses and corrections do not consume another distinct-version slot; no total-response or time limit is implied.`, "field-help"));
    }
    const permission = makeForm("Your permission choice", "Read the complete notice above. Neither choice is selected. Agree permits only the described local demo; Decline records the choice and does not open a response. Download and retain your exact copy.", "Record permission choice");
    codeField(permission.fields, "physician_code", "Your assigned physician code");
    field(permission.fields, "choice", "Permission choice", "select", "", {required: true, choices: [["", "Select Agree or Decline"], ["agree", "Agree to the described local demo"], ["decline", "Decline participation"]]});
    permissionEditor = wireMutation(permission, "/api/permissions", () => ({governance_id: policy.governance_id, ...Object.fromEntries(new FormData(permission.form))}), async result => {
      downloadJSON(result.receipt, `twin-lab-permission-${result.receipt.receipt_id}.json`);
      await refresh();
      info.textContent = result.receipt.choice === "agree" ? "Permission recorded. Your exact copy was offered for download. Select that receipt and your approved assignment below." : "Decline recorded. No case response was opened. Your exact copy was offered for download.";
    }, async () => {
      if (permissionEditor?.protectedDraft() && !window.confirm("Discard this permission draft or unconfirmed request and refresh?")) return;
      permissionEditor = null;
      await refresh();
    });
    human.append(permission.panel);
    const latest = new Map(governance.receipts.map(item => [item.physician_code, item.receipt_id]));
    const agreed = governance.receipts.filter(item => item.governance_id === policy.governance_id && item.choice === "agree" && latest.get(item.physician_code) === item.receipt_id);
    const receipt = field(human, "permission_receipt_id", "Recorded permission for this participant", "select", "", {choices: [["", "Select a recorded Agree receipt"], ...agreed.map(item => [item.receipt_id, `${item.physician_code} · ${item.recorded_at}`])]});
    if (agreed.some(item => item.receipt_id === previousReceipt)) receipt.value = previousReceipt;
    const assigned = field(human, "assignment_id", "Approved version-pinned assignment", "select", "", {choices: [["", "Select a matching assignment"]]});
    const fillAssignments = (preserve = assigned.value) => {
      const selected = agreed.find(item => item.receipt_id === receipt.value);
      assigned.replaceChildren();
      const choices = [["", "Select a matching assignment"]];
      for (const item of collection.assignments) {
        const version = catalog.versions.find(version => version.version_id === item.version_id);
        if (item.physician_code === selected?.physician_code && item.protocol_id === collection.current?.protocol_id && version?.latest_review?.disposition === "approved") choices.push([item.assignment_id, `${version.snapshot.title} · v${version.case_version}`]);
      }
      for (const [value, label] of choices) { const option = node("option", label); option.value = value; assigned.append(option); }
      if (choices.some(([value]) => value === preserve)) assigned.value = preserve;
    };
    fillAssignments(previousAssignment);
    receipt.addEventListener("change", () => fillAssignments());
    human.append(button("Open selected assigned case", () => onOpenAssignment(assigned.value), true));
    human.append(node("p", "Assignments must match the receipt's physician code and an approved exact case version. Use Collection plan to record assignments and Case lab to record actual content reviews. No assignment or approval is inferred.", "field-help"));
    if (previousReceipt && receipt.value !== previousReceipt) return " The selected permission is no longer available. Review the latest choice and select a current Agree receipt and matching assignment.";
    if (previousAssignment && assigned.value !== previousAssignment) return " The selected assignment is no longer available under the current plan and case review. Select a current approved assignment.";
    return "";
  }

  async function refresh() {
    const generation = ++refreshGeneration;
    container.setAttribute("aria-busy", "true");
    try {
      const result = await Promise.all([request("/api/governance"), request("/api/collection"), request("/api/catalog")]);
      if (generation !== refreshGeneration) return;
      [governance, collection, catalog] = result;
      const enabled = governance.readiness.actual_physician_capture_enabled && linkedPlanAvailable();
      mode.options[1].disabled = !enabled;
      info.textContent = enabled ? "Actual physician participation requires recorded permission and an approved assigned case. Study collection remains disabled." : "Actual physician participation is disabled. Complete and verify the local Governance requirements first. Only fabricated software testing is available.";
      if (governance.readiness.actual_physician_capture_enabled && !linkedPlanAvailable()) info.textContent = "Actual physician participation is unavailable: link the current collection plan to the current approved Governance revision. Review the notice and save a revised plan explicitly; earlier links are preserved.";
      if (!permissionEditor?.protectedDraft() && !correction) info.textContent += renderHuman();
    } catch (error) {
      if (generation !== refreshGeneration) return;
      governance = null;
      mode.options[1].disabled = true;
      info.textContent = `Could not verify participation requirements: ${error.message} Actual physician capture is unavailable. Refresh Governance to retry.`;
    } finally {
      if (generation === refreshGeneration) container.setAttribute("aria-busy", "false");
    }
  }

  function context(body, original = null) {
    const capture_mode = original ? original.capture_mode || "legacy_unclassified" : mode.value;
    if (original) {
      qa.hidden = capture_mode !== "fabricated_qa";
      human.hidden = true;
      mode.disabled = true;
      current.hidden = false;
      current.textContent = `Preparing correction: ${modeLabel(capture_mode)}. The original participation status is preserved.`;
    }
    if (capture_mode === "legacy_unclassified") return {capture_mode, permission_receipt_id: null, qa_acknowledged: false};
    if (capture_mode === "fabricated_qa") {
      if (!ack.checked) throw new Error("Acknowledge that this presentation is for fabricated software testing before opening a case or correction.");
      return {capture_mode, permission_receipt_id: null, qa_acknowledged: true};
    }
    if (!governance?.readiness.actual_physician_capture_enabled || !linkedPlanAvailable()) throw new Error("Actual physician participation is disabled. Review Governance and link the current collection plan to its current approved revision.");
    const permission_receipt_id = original?.permission_receipt_id || human.querySelector('[name="permission_receipt_id"]')?.value;
    if (!permission_receipt_id) throw new Error("Record or select the participant's Agree receipt first.");
    if (!original && !body.assignment_id) throw new Error("Choose an approved assigned case in the participation panel. General case browsing cannot open an actual physician response.");
    return {capture_mode, permission_receipt_id, qa_acknowledged: false};
  }

  function opened(presentation, original = null) {
    correction = original;
    ack.checked = false;
    mode.disabled = Boolean(original);
    current.hidden = false;
    current.textContent = `Current presentation: ${modeLabel(presentation.capture_mode || original?.capture_mode || "legacy_unclassified")}.${original ? " Correction preserves the original participation status and permission; it does not establish new or retrospective consent." : ""}`;
    if (original) {
      qa.hidden = presentation.capture_mode !== "fabricated_qa";
      human.hidden = true;
    }
  }

  function clearCorrection() {
    correction = null;
    mode.disabled = false;
    updateVisibility();
  }

  window.addEventListener("beforeunload", event => {
    if (permissionEditor?.protectedDraft()) { event.preventDefault(); event.returnValue = ""; }
  });
  return {refresh, context, opened, clearCorrection};
}

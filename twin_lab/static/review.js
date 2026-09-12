import {node, renderSnapshot} from "/snapshot.js";

export function renderResponses(container, responses, onCorrect) {
  container.replaceChildren();
  if (!responses.length) {
    const empty = node("div", undefined, "empty-state");
    empty.append(node("h2", "No responses available for ordinary review."), node("p", "There may be no saved responses, or existing records may be restricted. Governance shows response-chain restrictions and retained metadata."));
    container.append(empty);
    return;
  }
  const superseded = new Set(responses.map(item => item.supersedes_response_id).filter(Boolean));
  [...responses].reverse().forEach(response => {
    const card = node("article", undefined, "panel review-card");
    const heading = node("div", undefined, "section-top");
    const title = node("div");
    title.append(node("p", `${response.physician_code} · ${response.case_id} · v${response.case_version}`, "eyebrow"));
    title.append(node("h2", response.case_snapshot.title));
    heading.append(title, node("span", response.supersedes_response_id ? "Correction" : "Original", "subtle-tag"));
    card.append(heading, node("p", `Saved ${response.submitted_at}`, "small muted"));
    const participation = {fabricated_qa: "Fabricated software-test response", physician_demo: "Physician demo response with recorded permission", legacy_unclassified: "Legacy response — origin and permission unverified"}[response.capture_mode] || "Legacy response — origin and permission unverified";
    card.append(node("p", participation, "planning-review-state"));
    if (response.permission_receipt_id) card.append(node("p", `Permission receipt: ${response.permission_receipt_id} · Governance: ${response.governance_id || "See stored permission record"}`, "small identifier"));
    if (response.expires_at) card.append(node("p", `Response-chain expiry: ${response.expires_at} · Corrections do not restart retention.`, "small muted"));
    const values = node("dl", undefined, "saved-values");
    [
      ["Physician code (as submitted)", "physician_code"],
      ["Next action", "next_action"], ["Next information request", "next_information"],
      ["What would change the decision", "decision_change"],
      ["Brief rationale", "rationale"], ["Self-reported decision confidence", "confidence"],
    ].forEach(([label, key]) => {
      const item = node("div");
      const value = response.original_values[key];
      item.append(node("dt", label), node("dd", value === null || value === "" ? "Not recorded" : value));
      values.append(item);
    });
    card.append(values, node("p", `Response ID: ${response.response_id}`, "small identifier"));
    if (response.case_version_id) card.append(node("p", `Exact case version: ${response.case_version_id} · Review at presentation: ${response.case_review_id || "Unreviewed"}`, "small identifier"));
    if (response.assignment_id) card.append(node("p", `Demo assignment: ${response.assignment_id} · Protocol: ${response.protocol_id}`, "small identifier"));
    if (response.supersedes_response_id) {
      card.append(node("p", `Corrects response: ${response.supersedes_response_id}`, "small identifier"));
    }
    const snapshotDetails = node("details");
    snapshotDetails.append(node("summary", "Exact presented case"));
    const snapshotContent = node("div", undefined, "review-snapshot");
    renderSnapshot(snapshotContent, response.case_snapshot);
    snapshotDetails.append(snapshotContent);
    const recordDetails = node("details");
    recordDetails.append(node("summary", "Complete saved record and provenance"));
    recordDetails.append(node("pre", JSON.stringify(response, null, 2), "record-json"));
    card.append(snapshotDetails, recordDetails);
    if (superseded.has(response.response_id)) {
      card.append(node("p", "An appended correction supersedes this response. The original remains preserved.", "small muted"));
    } else {
      const correct = node("button", "Create correction", "secondary-button");
      correct.type = "button";
      correct.addEventListener("click", () => onCorrect(response));
      card.append(correct);
    }
    container.append(card);
  });
}

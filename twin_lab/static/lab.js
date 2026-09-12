import {request} from "/api.js";
import {node, renderSnapshot} from "/snapshot.js";
import {button, field, codeField, makeForm, wireMutation, mayDiscard, jsonDetails, versionChoices, heading} from "/planning-ui.js";

const dispositionText = value => ({approved: "Approved by local reviewer", needs_revision: "Needs revision", rejected: "Rejected"}[value] || "Unreviewed");

export function initLab(container, {onChange, onOpenVersion}) {
  let catalog = null;
  let selectedId = null;
  let editors = [];
  let status = null;
  let loading = false;

  async function refresh(force = false) {
    if (loading || (force && !mayDiscard(editors))) return;
    loading = true;
    if (status) { status.textContent = "Loading the local case catalog…"; status.classList.remove("error"); }
    try {
      catalog = await request("/api/catalog");
      if (!force && editors.some(editor => editor.protectedDraft())) {
        status.textContent = "The catalog has been refreshed. Your current form is retained; use Refresh to discard it and display the latest records.";
      } else render();
    } catch (error) {
      if (!status) status = heading(container, "LOCAL CONTENT WORKBENCH", "Case lab", "Review exact case versions and inspect matched synthetic families.", () => refresh(true));
      status.textContent = `Could not load the catalog: ${error.message} Use Refresh to retry.`;
      status.classList.add("error");
    } finally { loading = false; }
  }

  async function saved(result) {
    await onChange();
    if (result.version) selectedId = result.version.version_id;
    await refresh();
    if (status) status.textContent = `Save confirmed. ${status.textContent}`;
  }

  function renderReview(version) {
    const previous = version.latest_review;
    const ui = makeForm("Record a case review", "This judgment applies only to the exact version shown. Approval never enables study collection. Earlier reviews remain visible.", "Save review");
    codeField(ui.fields, "reviewer_code", "Reviewer code");
    field(ui.fields, "reviewed_on", "Review date (UTC)", "date", new Date().toISOString().slice(0, 10), {required: true, max: new Date().toISOString().slice(0, 10)});
    field(ui.fields, "disposition", "Disposition", "select", "", {required: true, choices: [["", "Select a disposition"], ["approved", "Approved by local reviewer"], ["needs_revision", "Needs revision"], ["rejected", "Rejected"]]});
    field(ui.fields, "comments", "Review comments", "textarea", "", {required: true, maxLength: 5000, help: "Record case-content issues, revisions needed, and the basis of the review. Do not enter patient information."});
    if (previous) ui.fields.append(node("p", `This appends a review linked to ${previous.review_id}; that review is preserved.`, "identifier"));
    editors.push(wireMutation(ui, "/api/case-reviews", () => {
      const values = Object.fromEntries(new FormData(ui.form));
      return {...values, version_id: version.version_id, supersedes_review_id: previous?.review_id ?? null};
    }, saved, () => refresh(true)));
    return ui.panel;
  }

  function renderVersionForm(version) {
    const ui = makeForm("Create a new case version", "Edit the latest version to append a revision. Case identity, family, and earlier snapshots are preserved. New content starts unreviewed and remains demo-only.", "Save new version");
    field(ui.fields, "version", "New version label", "text", "", {required: true, maxLength: 64, pattern: "[A-Za-z0-9._\\-]{1,64}", help: "Use a new, unused label. Do not reuse a saved version."});
    codeField(ui.fields, "editor_code", "Editor code");
    field(ui.fields, "change_note", "Change note", "textarea", "", {required: true, maxLength: 5000});
    for (const [key, label, type] of [["title", "Case title", "text"], ["narrative", "Visible narrative", "textarea"], ["care_setting", "Care setting", "text"], ["provenance", "Provenance", "textarea"]]) {
      field(ui.fields, key, label, type, version.snapshot[key], {required: true, maxLength: 12000});
    }
    ui.fields.append(node("h3", "Decision-time facts"));
    version.snapshot.decision_time_facts.forEach((fact, index) => field(ui.fields, `fact_${index}`, fact.label, "textarea", fact.value, {required: true, maxLength: 2000}));
    ui.fields.append(node("p", `Case ${version.case_id} · Family ${version.snapshot.family_id}`, "identifier"));
    editors.push(wireMutation(ui, "/api/case-versions", () => {
      const values = Object.fromEntries(new FormData(ui.form));
      const snapshot = structuredClone(version.snapshot);
      for (const key of ["title", "narrative", "care_setting", "provenance"]) snapshot[key] = values[key];
      snapshot.version = values.version;
      snapshot.decision_time_facts.forEach((fact, index) => { fact.value = values[`fact_${index}`]; });
      return {based_on_version_id: version.version_id, version: values.version, editor_code: values.editor_code, change_note: values.change_note, snapshot};
    }, saved, () => refresh(true)));
    return ui.panel;
  }

  function renderHistory(version) {
    const panel = node("article", undefined, "panel planning-card");
    panel.append(node("h2", "Preserved version and review history"));
    for (const item of catalog.versions.filter(item => item.case_id === version.case_id)) {
      const record = node("div", undefined, "planning-record");
      record.append(node("h3", `Version ${item.case_version} · ${dispositionText(item.latest_review?.disposition)}`));
      record.append(node("p", `Created ${item.created_at} · Editor ${item.editor_code || "Source fixture"}`, "small muted"));
      record.append(node("p", item.change_note || "Imported synthetic source fixture."));
      record.append(button("Inspect this version", () => selectVersion(item.version_id)));
      const reviews = catalog.reviews.filter(review => review.version_id === item.version_id);
      if (!reviews.length) record.append(node("p", "No local review has been recorded.", "small muted"));
      for (const review of reviews) {
        const reviewRecord = node("div", undefined, "planning-record");
        reviewRecord.append(node("h3", `${dispositionText(review.disposition)} · ${review.reviewed_on}`));
        reviewRecord.append(node("p", `Reviewer ${review.reviewer_code} · Recorded ${review.recorded_at}`, "small muted"));
        reviewRecord.append(node("p", review.comments), jsonDetails("Review record and revision link", review));
        record.append(reviewRecord);
      }
      record.append(jsonDetails("Exact stored case version", item));
      panel.append(record);
    }
    return panel;
  }

  function renderFamilies() {
    const panel = node("article", undefined, "panel planning-card");
    panel.append(node("h2", "Matched synthetic families"), node("p", "These fixed source pairs demonstrate one declared fact change. They are unreviewed examples, not a validated experimental design. Later revisions do not rewrite these comparisons. Comparison hints appear only in Case lab.", "small muted"));
    for (const family of catalog.families) {
      const base = catalog.versions.find(item => item.version_id === family.base_version_id);
      const variant = catalog.versions.find(item => item.version_id === family.variant_version_id);
      const details = node("details");
      details.append(node("summary", `${family.title} · ${family.factor_label}`));
      const changed = family.changed_fact;
      details.append(node("h3", `Declared change: ${changed.label}`));
      const comparison = node("dl", undefined, "planning-facts");
      for (const [label, value] of [["Base", changed.base_value], ["Variant", changed.variant_value]]) {
        const fact = node("div");
        fact.append(node("dt", label), node("dd", value));
        comparison.append(fact);
      }
      details.append(comparison, node("h3", "Held constant"));
      const held = node("ul", undefined, "planning-list");
      family.held_constant.forEach(item => held.append(node("li", item)));
      details.append(held);
      const actions = node("div", undefined, "planning-actions");
      if (base) actions.append(button(`Inspect base · v${base.case_version}`, () => selectVersion(base.version_id)));
      if (variant) actions.append(button(`Inspect variant · v${variant.case_version}`, () => selectVersion(variant.version_id)));
      details.append(actions, jsonDetails("Version-pinned family record", family));
      panel.append(details);
    }
    return panel;
  }

  function selectVersion(id) {
    if (!mayDiscard(editors)) return;
    selectedId = id;
    render();
    container.scrollIntoView({behavior: "smooth", block: "start"});
  }

  function render() {
    editors = [];
    container.replaceChildren();
    status = heading(container, "LOCAL CONTENT WORKBENCH", "Case lab", "Review exact case versions, preserve revisions, and inspect matched synthetic families. All cases remain ineligible for study.", () => refresh(true));
    if (!catalog.versions.length) { status.textContent = "No case versions are available."; return; }
    const firstCaseVersions = catalog.versions.filter(item => item.case_id === catalog.versions[0].case_id);
    const version = catalog.versions.find(item => item.version_id === selectedId) || firstCaseVersions.at(-1);
    selectedId = version.version_id;
    const stack = node("div", undefined, "planning-stack");
    const chosen = node("article", undefined, "panel planning-card");
    const selector = field(chosen, "case_version", "Case and exact version", "select", selectedId, {choices: versionChoices(catalog.versions)});
    selector.addEventListener("change", () => { const id = selector.value; selector.value = selectedId; selectVersion(id); });
    const snapshot = node("div");
    renderSnapshot(snapshot, version.snapshot);
    chosen.append(snapshot);
    chosen.append(node("p", `Local review: ${dispositionText(version.latest_review?.disposition)}. This does not change study eligibility or the source snapshot.`, "planning-review-state"));
    chosen.append(node("p", `Version ID ${version.version_id} · Snapshot SHA-256 ${version.snapshot_sha256}`, "identifier"));
    chosen.append(button("Open this version for a demo response", () => onOpenVersion(version.version_id)));
    stack.append(chosen);
    const forms = node("div", undefined, "planning-columns");
    forms.append(renderReview(version));
    if (!catalog.versions.some(item => item.based_on_version === version.version_id)) forms.append(renderVersionForm(version));
    else {
      const preserved = node("article", undefined, "panel planning-card");
      preserved.append(node("h2", "Preserved earlier version"), node("p", "Select the latest version of this case to create a revision. You can still inspect, review, or open this exact earlier version for a demo response.", "small muted"));
      forms.append(preserved);
    }
    stack.append(forms, renderHistory(version), renderFamilies());
    container.append(stack);
  }

  window.addEventListener("beforeunload", event => {
    if (editors.some(editor => editor.protectedDraft())) { event.preventDefault(); event.returnValue = ""; }
  });
  return refresh;
}

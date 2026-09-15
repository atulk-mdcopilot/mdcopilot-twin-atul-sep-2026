import {node, renderSnapshot} from "/snapshot.js";
import {renderResponses} from "/review.js";
import {request} from "/api.js";
import {initLab} from "/lab.js";
import {initCollection} from "/collection.js";
import {initGovernance} from "/governance.js";
import {initCaptureMode} from "/capture-mode.js";

const $ = id => document.getElementById(id);
const form = $("response-form");
const fields = $("response-fields");
const saveButton = $("save-response");
const state = {presentation: null, pending: null, requestedPresentation: null, saving: false, opening: false, saved: false, baseline: "", reviewLoading: false};
const refreshLab = initLab($("cases-view"), {onChange: loadCases, onOpenVersion: version_id => openPresentation({version_id})});
const refreshCollection = initCollection($("collection-view"), {onOpenAssignment: assignment_id => openPresentation({assignment_id})});
const captureMode = initCaptureMode($("capture-mode"), {onOpenAssignment: assignment_id => openPresentation({assignment_id}), onModeChange: () => {
  if (!mayReplace()) return false;
  state.presentation = null;
  state.pending = null;
  state.saved = false;
  state.requestedPresentation = null;
  form.reset();
  fields.disabled = true;
  saveButton.disabled = true;
  $("case-display").replaceChildren();
  $("retry-presentation").hidden = true;
  message("presentation-status", "Select a case for this capture mode.");
  message("save-status", "");
  return true;
}});
const refreshGovernance = initGovernance($("governance-view"), () => captureMode.refresh());
const reviewLabel = value => ({approved: "Locally approved", needs_revision: "Needs revision", rejected: "Rejected"}[value] || "Unreviewed");

function values() {
  return Object.fromEntries(["physician_code", "next_action", "next_information", "decision_change", "rationale", "confidence"].map(key => [key, key === "confidence" ? form.elements[key].value || null : form.elements[key].value]));
}

function dirty() {
  return Boolean(state.pending || (state.presentation && !state.saved && JSON.stringify(values()) !== state.baseline));
}

function mayReplace() {
  if (state.saving || state.opening) return false;
  if (!dirty()) return true;
  const message = state.pending ? "This save has not been confirmed. Retry the unchanged save or review local records to check it. Leave this response anyway?" : "Discard the unsaved response and open another case?";
  return window.confirm(message);
}

function message(id, text, error = false) {
  $(id).textContent = text;
  $(id).classList.toggle("error", error);
}

function showView(view) {
  for (const name of ["capture", "review", "cases", "collection", "governance"]) {
    const selected = name === view;
    $(`${name}-view`).hidden = !selected;
    $(`${name}-tab`).classList.toggle("active", selected);
    if (selected) $(`${name}-tab`).setAttribute("aria-current", "page");
    else $(`${name}-tab`).removeAttribute("aria-current");
  }
  if (view === "review") loadResponses();
  if (view === "cases") refreshLab();
  if (view === "collection") refreshCollection();
  if (view === "governance") refreshGovernance();
  if (view === "capture") captureMode.refresh();
}

async function openPresentation(body, correction = null) {
  if (!mayReplace()) return;
  state.requestedPresentation = {body, correction};
  let participation;
  if (!correction) captureMode.clearCorrection();
  try { participation = captureMode.context(body, correction); }
  catch (error) {
    showView("capture");
    message("presentation-status", error.message, true);
    $("retry-presentation").hidden = false;
    return;
  }
  state.opening = true;
  fields.disabled = true;
  saveButton.disabled = true;
  showView("capture");
  message("presentation-status", "Loading the case and recording its presentation…");
  try {
    const presentation = await request("/api/presentations", {...body, ...participation});
    const code = form.elements.physician_code.value;
    state.presentation = presentation;
    state.pending = null;
    state.saved = false;
    captureMode.opened(presentation, correction);
    state.requestedPresentation = null;
    $("retry-presentation").hidden = true;
    form.reset();
    form.elements.physician_code.value = presentation.assigned_physician_code ?? code;
    if (correction) {
      Object.entries(correction.original_values).forEach(([key, value]) => { form.elements[key].value = value ?? ""; });
    }
    form.elements.physician_code.readOnly = Boolean(correction || presentation.assigned_physician_code);
    for (const input of fields.querySelectorAll("input, textarea")) input.setCustomValidity("");
    state.baseline = JSON.stringify(values());
    renderSnapshot($("case-display"), presentation.case_snapshot);
    for (const button of $("case-list").children) {
      const active = button.dataset.caseId === presentation.case_snapshot.case_id && button.dataset.caseVersion === presentation.case_snapshot.version;
      button.classList.toggle("selected", active);
      button.setAttribute("aria-pressed", String(active));
    }
    $("correction-notice").hidden = !correction;
    $("correction-notice").textContent = correction ? `Correcting response ${correction.response_id}. The original case snapshot and physician code are retained. Saving appends a revision.` : "";
    $("assignment-notice").hidden = !presentation.assignment_id;
    $("assignment-notice").textContent = presentation.assignment_id ? `Demo assignment ${presentation.assignment_id}. The physician code, case version, and protocol are pinned. Participation status and any permission receipt are stored separately. Study collection remains disabled.` : "";
    message("presentation-status", `Presented ${presentation.presented_at} · Complete visible case snapshot below.`);
    message("save-status", "");
    $("new-response").hidden = true;
    saveButton.textContent = correction ? "Save correction →" : "Save response →";
  } catch (error) {
    message("presentation-status", `Could not open the case: ${error.message} Select the case or correction again to retry.`, true);
    $("retry-presentation").hidden = false;
  } finally {
    state.opening = false;
    fields.disabled = !state.presentation || state.saved || Boolean(state.pending);
    saveButton.disabled = !state.presentation || state.saved;
  }
}

async function loadCases() {
  $("reload-cases").hidden = true;
  message("cases-status", "Loading cases…");
  try {
    const {cases} = await request("/api/cases");
    $("case-list").replaceChildren();
    $("case-count").textContent = String(cases.length).padStart(2, "0");
    cases.forEach((item, index) => {
      const button = node("button", undefined, "case-button");
      button.type = "button";
      button.dataset.caseId = item.case_id;
      button.dataset.caseVersion = item.version;
      const active = item.case_id === state.presentation?.case_snapshot.case_id && item.version === state.presentation?.case_snapshot.version;
      button.classList.toggle("selected", active);
      button.setAttribute("aria-pressed", String(active));
      button.append(node("span", `CASE ${String(index + 1).padStart(2, "0")} · v${item.version}`, "case-index"), node("strong", item.title), node("span", item.care_setting, "case-setting"), node("span", reviewLabel(item.review_status), "case-setting"));
      button.addEventListener("click", () => openPresentation({case_id: item.case_id}));
      $("case-list").append(button);
    });
    message("cases-status", `${cases.length} synthetic demo cases. Review status applies to each version. All remain ineligible for study.`);
  } catch (error) {
    message("cases-status", `Could not load cases: ${error.message}`, true);
    $("reload-cases").hidden = false;
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (!state.presentation || state.saving || state.saved || state.opening) return;
  if (!state.pending) {
    for (const key of ["physician_code", "next_action", "next_information", "decision_change"]) {
      const input = form.elements[key];
      input.setCustomValidity(input.value.trim() ? "" : "Enter a response; spaces alone cannot be saved.");
    }
    const code = form.elements.physician_code;
    if (code.value.trim() && !/^[A-Za-z0-9_-]{1,40}$/.test(code.value.trim())) code.setCustomValidity("Use 1–40 letters, numbers, underscores, or hyphens for the physician code.");
    if (!form.reportValidity()) return;
    state.pending = {presentation_id: state.presentation.presentation_id, values: values()};
  }
  state.saving = true;
  fields.disabled = true;
  saveButton.disabled = true;
  saveButton.textContent = "Saving…";
  message("save-status", "Waiting for the local database to confirm the save…");
  try {
    const {response, duplicate} = await request("/api/responses", state.pending);
    state.saved = true;
    state.pending = null;
    message("save-status", `${duplicate ? "Existing save confirmed" : "Saved locally"} at ${response.submitted_at}. Response ID: ${response.response_id}.`);
    saveButton.textContent = "Saved";
    $("new-response").hidden = false;
    if (!$("review-view").hidden) loadResponses();
  } catch (error) {
    if (error.status >= 400 && error.status < 500 && error.status !== 409) {
      state.pending = null;
      fields.disabled = false;
      saveButton.textContent = "Save response →";
      message("save-status", `Response was not saved: ${error.message} Update the fields and try again.`, true);
    } else if (error.status === 409) {
      saveButton.textContent = "Retry unchanged save";
      message("save-status", `Save conflict: ${error.message} Use Review responses and Governance to inspect saved records or participation restrictions before retrying.`, true);
    } else {
      saveButton.textContent = "Retry unchanged save";
      message("save-status", `Save not confirmed: ${error.message} Your entered values are held unchanged. Retry after the server is available; an unchanged retry cannot add a duplicate.`, true);
    }
  } finally {
    state.saving = false;
    saveButton.disabled = state.saved;
  }
});

form.addEventListener("input", event => {
  if (typeof event.target.setCustomValidity === "function") event.target.setCustomValidity("");
});

async function loadResponses() {
  if (state.reviewLoading) return;
  state.reviewLoading = true;
  $("refresh-responses").disabled = true;
  message("review-status", "Loading saved observations…");
  try {
    const {responses} = await request("/api/responses");
    $("response-count").textContent = `${responses.length} ${responses.length === 1 ? "response" : "responses"} available for review, including corrections`;
    renderResponses($("response-list"), responses, response => openPresentation({supersedes_response_id: response.response_id}, response));
    message("review-status", "");
  } catch (error) {
    $("response-list").replaceChildren();
    $("response-count").textContent = "Responses unavailable";
    message("review-status", `Could not load local responses: ${error.message} Use Refresh to try again.`, true);
  } finally {
    state.reviewLoading = false;
    $("refresh-responses").disabled = false;
  }
}

form.elements.physician_code.maxLength = 128;
for (const key of ["next_action", "next_information", "decision_change", "rationale"]) form.elements[key].maxLength = 5000;
$("capture-tab").addEventListener("click", () => showView("capture"));
$("review-tab").addEventListener("click", () => showView("review"));
$("cases-tab").addEventListener("click", () => showView("cases"));
$("collection-tab").addEventListener("click", () => showView("collection"));
$("governance-tab").addEventListener("click", () => showView("governance"));
$("refresh-responses").addEventListener("click", loadResponses);
$("reload-cases").addEventListener("click", loadCases);
$("retry-presentation").addEventListener("click", () => {
  if (state.requestedPresentation) openPresentation(state.requestedPresentation.body, state.requestedPresentation.correction);
});
$("new-response").addEventListener("click", () => {
  const presentation = state.presentation;
  const body = presentation.assignment_id ? {assignment_id: presentation.assignment_id}
    : presentation.case_version_id ? {version_id: presentation.case_version_id}
      : {case_id: presentation.case_snapshot.case_id};
  openPresentation(body);
});
window.addEventListener("beforeunload", event => {
  if (dirty() || state.saving) { event.preventDefault(); event.returnValue = ""; }
});
loadCases();
captureMode.refresh();

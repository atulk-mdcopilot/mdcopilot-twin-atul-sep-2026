import {request} from "/api.js";
import {node} from "/snapshot.js";

let nextField = 0;

export function button(text, action, primary = false) {
  const result = node("button", text, primary ? "primary-button" : "secondary-button");
  result.type = "button";
  result.addEventListener("click", action);
  return result;
}

export function field(parent, name, label, type = "text", value = "", options = {}) {
  const group = node("div", undefined, "planning-field");
  const input = node(type === "textarea" || type === "select" ? type : "input");
  input.id = `planning-field-${++nextField}`;
  input.name = name;
  if (input.tagName === "INPUT") input.type = type;
  if (options.choices) {
    for (const [key, text] of options.choices) {
      const choice = node("option", text);
      choice.value = key;
      input.append(choice);
    }
  }
  input.value = value ?? "";
  for (const key of ["required", "maxLength", "min", "max", "step", "pattern", "rows"]) {
    if (options[key] !== undefined) input[key] = options[key];
  }
  const caption = node("label", label);
  caption.htmlFor = input.id;
  group.append(caption, input);
  if (options.help) {
    const help = node("p", options.help, "field-help");
    help.id = `${input.id}-help`;
    input.setAttribute("aria-describedby", help.id);
    group.append(help);
  }
  parent.append(group);
  return input;
}

export function codeField(parent, name, label, value = "", required = true) {
  return field(parent, name, label, "text", value, {
    required, maxLength: 40, pattern: "[A-Za-z0-9_\\-]{1,40}",
    help: "1–40 letters, numbers, underscores, or hyphens. Use a code, not a name or email.",
  });
}

export function checkField(parent, name, label, checked = false) {
  const group = node("label", undefined, "check-field");
  const input = node("input");
  input.type = "checkbox";
  input.name = name;
  input.checked = checked;
  group.append(input, node("span", label));
  parent.append(group);
  return input;
}

export function makeForm(title, description, saveLabel) {
  const panel = node("article", undefined, "panel planning-card");
  const form = node("form");
  const fields = node("fieldset");
  const save = node("button", saveLabel, "primary-button");
  save.type = "submit";
  const status = node("p", "", "save-status");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const footer = node("div", undefined, "planning-actions");
  footer.append(save);
  form.append(fields, footer, status);
  panel.append(node("h2", title), node("p", description, "small muted"), form);
  return {panel, form, fields, footer, save, status, saveLabel};
}

export function wireMutation(ui, path, build, onSaved, onReload) {
  let pending = null;
  let busy = false;
  const values = () => JSON.stringify(Array.from(ui.fields.querySelectorAll("input,textarea,select"), item => [item.name, item.type === "checkbox" ? item.checked : item.value]));
  let baseline = values();
  const protectedDraft = () => busy || pending !== null || values() !== baseline;
  const reset = button("Discard this draft and refresh", () => { if (!busy) onReload(); });
  reset.hidden = true;
  ui.footer.append(reset);
  ui.form.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    ui.status.classList.remove("error");
    if (!pending) {
      if (!ui.form.reportValidity()) return;
      try { pending = {request_id: crypto.randomUUID(), ...build()}; }
      catch (error) { ui.status.textContent = error.message; ui.status.classList.add("error"); return; }
    }
    busy = true;
    ui.fields.disabled = true;
    ui.save.disabled = true;
    reset.disabled = true;
    ui.save.textContent = "Saving…";
    ui.status.textContent = "Waiting for the local database to confirm this save…";
    let saved = null;
    try {
      const result = await request(path, pending);
      pending = null;
      baseline = values();
      saved = result;
      ui.status.textContent = result.duplicate ? "The existing local save was confirmed." : "Saved locally. Earlier records remain preserved.";
      ui.save.textContent = ui.saveLabel;
      reset.hidden = true;
    } catch (error) {
      ui.status.classList.add("error");
      reset.hidden = false;
      if (error.status >= 400 && error.status < 500 && error.status !== 409) {
        pending = null;
        ui.save.textContent = ui.saveLabel;
        ui.status.textContent = `Not saved: ${error.message} Update the fields and try again.`;
      } else {
        ui.save.textContent = "Retry unchanged save";
        ui.status.textContent = error.status === 409
          ? `Save conflict: ${error.message} Refresh to inspect current records before making a new submission.`
          : `Save not confirmed: ${error.message} The request is held unchanged. Retry to confirm it without creating a duplicate.`;
      }
    } finally {
      busy = false;
      ui.fields.disabled = pending !== null;
      ui.save.disabled = false;
      reset.disabled = false;
    }
    if (saved) await onSaved(saved);
  });
  return {protectedDraft, busy: () => busy};
}

export function mayDiscard(editors) {
  if (editors.some(editor => editor.busy())) return false;
  return !editors.some(editor => editor.protectedDraft()) || window.confirm("Discard unsaved fields or an unconfirmed request and refresh? If a save was unconfirmed, inspect the saved records before submitting again.");
}

export function jsonDetails(title, data) {
  const details = node("details");
  details.append(node("summary", title), node("pre", JSON.stringify(data, null, 2), "record-json"));
  return details;
}

export function versionChoices(versions) {
  return versions.map(version => [version.version_id, `${version.snapshot.title} · v${version.case_version}`]);
}

export function heading(container, eyebrow, title, description, refresh) {
  const top = node("div", undefined, "page-heading");
  const text = node("div");
  text.append(node("p", eyebrow, "eyebrow"), node("h1", title), node("p", description, "lede"));
  top.append(text, button("Refresh", refresh));
  container.append(top);
  const status = node("p", "", "small muted");
  status.setAttribute("role", "status");
  container.append(status);
  return status;
}

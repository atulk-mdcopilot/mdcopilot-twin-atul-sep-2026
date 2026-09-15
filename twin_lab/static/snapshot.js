// Safe shared rendering for the visible case and stored response snapshots.
export function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

export function renderSnapshot(container, snapshot) {
  container.replaceChildren();
  const tags = node("div", undefined, "snapshot-tags");
  const review = {approved: "Locally approved", needs_revision: "Needs revision", rejected: "Rejected", unreviewed: "Unreviewed"}[snapshot.review_status] || snapshot.review_status;
  for (const text of ["Synthetic", review, "Not eligible for study"]) {
    tags.append(node("span", text, "subtle-tag"));
  }
  container.append(tags, node("h2", snapshot.title, "case-title"));
  container.append(node("p", snapshot.narrative, "case-narrative"));
  container.append(node("h3", "Decision-time facts", "facts-heading"));
  const facts = node("dl", undefined, "facts-grid");
  snapshot.decision_time_facts.forEach(({label, value}) => {
    const item = node("div");
    item.append(node("dt", label), node("dd", value));
    facts.append(item);
  });
  container.append(facts, node("h3", "Case details", "metadata-heading"));
  const metadata = node("dl", undefined, "metadata-grid");
  const fields = [
    ["Case ID", "case_id"], ["Case family", "family_id"],
    ["Case version", "version"], ["Care setting", "care_setting"],
    ["Synthetic", "synthetic"],
    ["Review status", "review_status"], ["Eligible for study", "eligible_for_study"],
    ["Collection purpose", "collection_purpose"],
  ];
  fields.forEach(([label, key]) => {
    const item = node("div");
    item.append(node("dt", label), node("dd", String(snapshot[key])));
    metadata.append(item);
  });
  const provenance = node("section", undefined, "case-provenance");
  provenance.append(
    node("h3", "Data provenance", "metadata-heading"),
    node("p", snapshot.provenance),
  );
  container.append(metadata, provenance);
}

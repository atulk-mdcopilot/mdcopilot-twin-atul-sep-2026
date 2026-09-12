# Twin Lab local scope

The original acceptance criteria are in
[the first-build brief](../MDcopilot_Twin_First_Build.md); the authorized extension
is specified in [milestone-2.md](milestone-2.md), with governance and lifecycle
controls specified in [milestone-3.md](milestone-3.md).
Twin Lab is a standalone, single-user local workbench for observing a physician's
unaided responses to synthetic adult GI-bleeding cases after initial stabilization.
It is a synthetic-case prototype, not a validated clinical tool or a learned
physician twin.

## Included

- Five original newly authored UI/demo fixtures, each marked synthetic,
  `unreviewed`, `eligible_for_study: false`, and `collection_purpose: demo`.
  These were not recovered from an original case workbook or patient records.
- Stable case and family identifiers, case versions, provenance, care setting,
  narrative, and structured decision-time facts. All case fields are visible.
- Required physician code, next action, next information request, and what would
  change the decision; optional brief rationale and self-reported decision
  confidence. Free text allows an explicit insufficient-information response.
- Local SQLite persistence of server-issued presentations and validated
  responses, preserving exact submitted values separately from trimmed values.
- Saved case snapshots, content hashes, case/version/schema metadata, timestamps,
  and explicit record of no AI advice being shown.
- Idempotent save retries and append-only, linked corrections that preserve
  original observations. Local review and versioned JSON export retain history.
- Local loopback access, documented setup, dependency pinning, data exclusion
  rules, automated tests, and restart verification.
- Five matched variants, creating ten case identities across five families.
  Each pair explicitly declares its one changed structured fact and information
  held constant. Definitions pin the exact original versions. Family comparison
  information appears in local authoring/review, not as advice during capture.
- Local reviewer code, review date, comments, and disposition attached to exact
  case versions. Later reviews append linked judgments; case revisions preserve
  original clinical content, identity, provenance, and response snapshots.
  New versions start unreviewed. Approval alone never grants study eligibility.
- Versioned draft collection rules for physician codes, manual case assignment,
  consent statement/version, retention, backup ownership/frequency/retention,
  and notes. Missing rules remain visible rather than receiving invented defaults.
  Assignments pin existing codes, protocols, and exact case versions.
- Manual verified local SQLite backups with an offline restore-to-new-file
  procedure, and migration of original response records without rewriting them.
  JSON export now retains catalog, review, family, protocol, and assignment history.
- Project-user-approved demo governance documents and policy choices, versioned
  operational approval attestations, exact
  participant permission receipts and copies, and a server-enforced distinction
  between explicitly fabricated tests and permitted local physician demo capture.
- Frozen original-chain expiry, withdrawal restrictions, scoped holds, managed
  copy inventory, explicit offline disposal, and restoration that reapplies
  current restrictions/deletions from external journals. Historical records
  gain no inferred permission or retention policy.

The case count and selected variations are software-testing conveniences. They
are not a research sample or a validated matched-case design. Source narratives
have no clinical-review approval. Case plausibility,
elicitation quality, and suitability for study cannot be certified by software
tests. The next human review concerns case content, the form, and provenance.

## Excluded

No clinical recommendation, suggested diagnosis, answer key, presumed correct
decision, diagnostic probability, outcome label, or physician preference is
provided. Confidence describes the user's decision confidence, not disease
probability. The form does not request detailed private reasoning.

There is no LLM API, training, fine-tuning, prediction, model comparison, guideline
retrieval, multi-agent orchestration, automated case selection, analytics,
telemetry, patient data, EHR integration, cloud synchronization, public hosting,
deployed authentication infrastructure, billing, or clinical ordering.

Actual study collection remains excluded. There is no endpoint or configuration
switch to enable it. Demo permission is separate from research consent or study
authorization. Physician-code assignment does not authenticate a person.
Physical disposal requires an explicit offline plan; scheduling, remote backup,
and restore-over-live-data endpoints are not implemented. Device encryption,
control of detached copies and administrative record retention require documented
operator procedures. The explicit project-user approval recorded at
2026-09-10T23:33:19Z adopts the incorporated demo documents and policy choices.
It does not infer missing operator details, accepted role appointments, qualified
review, control verification or participant agreement. Those operational records
must still be completed, and the participant notice must match implemented and
verified controls. One-calendar-year administrative policies require reviewed
day-count mapping once the pilot close date is known. Original Downloads files,
legacy response provenance and existing retention anchors remain unchanged.

## Future MDcopilot integration boundary

This repository does not import or call the separate MDcopilot application's
code, APIs, databases, or credentials. The versioned JSON contract in
[schema.md](schema.md) is a possible future review boundary, not an implemented
integration. Any later import/export adapter needs a separate specification,
authorization, data-governance review, and explicit schema mapping. No patient
system should be connected to this prototype.

## Local-use limitations

The service publishes only on `127.0.0.1`. It has no user authentication, account
isolation, encryption at rest, or tamper-proof audit log. Physician codes are
labels, not verified identities. Anyone with local access to the service or its
data files can inspect response data. Application-level append-only behavior
does not prevent direct modification of SQLite files. Keep the app on one
trusted local machine and keep responses and exports outside the repository.

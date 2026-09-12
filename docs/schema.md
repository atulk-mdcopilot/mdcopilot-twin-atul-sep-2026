# Twin Lab data contract v1.2

The [governance/lifecycle contract](milestone-3.md) defines the current additions.
New presentations require explicit capture mode, permission reference and QA
acknowledgment. New responses add governance/permission references under schema
1.2; existing saved payloads retain their original schema and values. SQLite
versions 1/2 migrate to 3. General managed export is 1.2, excludes restricted
response chains and private governance/permission documents, and adds its copy
manifest. The sections below retain the earlier contracts as historical context;
where they differ, milestone 3 governs current behavior.

All JSON is UTF-8. Unknown keys are rejected at input boundaries. Response and
presentation IDs are UUIDs; timestamps are server-generated ISO 8601 UTC strings.
Validation uses the Python standard library. Schema v1.1 adds immutable case
review/version records and demo collection planning; it does not rewrite v1.0
saved response objects. The original shapes are documented first for existing
records; the extension and current export are specified below.

## Synthetic fixture / visible snapshot

Required keys: `case_id`, `family_id`, `version`, `title`, `provenance`,
`care_setting`, `narrative` (nonempty strings), `decision_time_facts` (nonempty list
of `{label, value}` nonempty strings), `synthetic: true`,
`review_status: "unreviewed"`, `eligible_for_study: false`,
`collection_purpose: "demo"`. No answer keys, outcomes, diagnoses-as-labels, or
hidden fields are accepted. Fixtures are newly authored software placeholders.

## Local HTTP interface

- `GET /api/cases` → `{cases: [snapshot, ...]}`.
- `POST /api/presentations` with `{case_id}` → presentation below.
- For a correction, POST `{supersedes_response_id}` instead; this presents the
  original saved snapshot even if the fixture changed since submission.
- `POST /api/responses` with `{presentation_id, values}` → `{response, duplicate}`.
  `values` has exactly `physician_code`, `next_action`, `next_information`,
  `decision_change`, `rationale`, `confidence`. The first four are required text;
  rationale may be empty. Confidence is `null`, `"low"`, `"moderate"`, or `"high"`,
  and denotes self-reported decision confidence, not a probability.
- `GET /api/responses` → `{responses: [...]}`, oldest first, including originals
  and corrections. The local user can review all codes; codes are not accounts.
- `GET /api/export` → downloadable versioned JSON with all responses/revisions.

Writes require `Content-Type: application/json` and `X-Twin-Lab: 1`. Browser
requests must be same-origin. No CORS is enabled. HTTP errors use `{error: text}`.
An unchanged retry returns the same observation. Reusing a presentation with
different values is a conflict (409); create an explicit correction instead.
Only the latest revision can be corrected, by the same normalized physician code.

Text fields permit at most 5,000 characters each. The raw physician-code field
permits 128 characters; after trimming it must be 1–40 ASCII letters, digits,
underscores or hyphens. Leading/trailing whitespace is retained in original
values. The HTTP body limit is 128 KiB, including JSON encoding. Empty required
text, control characters (except tab/newline), duplicate JSON keys, and malformed
Unicode are rejected. Case/family/version identifiers are stable strings of at
most 64 ASCII letters, digits, dots, underscores or hyphens (fixtures use UUIDs
for case/family IDs). Presentation and response IDs are canonical UUIDs.

## Legacy v1.0 presentation

`presentation_id`, `presented_at`, `case_snapshot`, `snapshot_sha256`, and
`supersedes_response_id` (UUID or null). Presentation is persisted before delivery.
`presented_at` is when the server issues the case, not proof of visual attention.
The browser displays the complete case snapshot with no extra clinical content.
SHA-256 uses JSON with sorted keys, separators `,` and `:`, and `ensure_ascii=False`.

## Legacy v1.0 saved response (retained unchanged)

`response_id`, `presentation_id`, `physician_code` (trimmed), `case_id`,
`case_family`, `case_version`, `response_schema_version: "1.0"`,
`case_snapshot`, `snapshot_sha256`, `presented_at`, `submitted_at`,
`original_values` (exact validated submitted strings/null), `normalized_values`
(trimmed strings, same confidence), `ai_advice_shown: false`,
`collection_purpose: "demo"`, `case_review_status: "unreviewed"`,
`eligible_for_study: false`, and `supersedes_response_id` (UUID or null).

## Legacy v1.0 export envelope

`export_schema_version: "1.0"`, `exported_at`,
`application: "Twin Lab v0.1"`, `synthetic_only: true`,
`response_count` (integer), and `responses` (complete saved response objects).
Export includes every original and linked revision; it does not collapse history.
Export timestamps change between downloads; saved response objects do not.
Exports contain physician response data and must remain outside version control.

## Current catalog and immutable versions

`GET /api/catalog` returns `{versions, reviews, families}`. The catalog starts
with the original five fixtures plus five variants. `GET /api/cases` returns
the latest snapshot for each of the ten case identities, with review status
derived from the latest local review; all remain synthetic, demo, and ineligible.
Source snapshots themselves remain marked unreviewed. The presented snapshot
and hash include exactly the review status shown at presentation time.

The default catalog appends source wording revision 1.1 after importing the
original 1.0 snapshots. This removes “fictional” from narratives and fact text,
retaining clinical values and provenance. A fresh catalog therefore has twenty
version records across ten case identities. Existing local revisions are never
replaced by this source copy edit. Original family definitions and prior
presentations/responses keep their exact original versions and wording.

A version has `version_id`, `case_id`, `case_version`, `snapshot`,
`snapshot_sha256`, `created_at`, `editor_code`, `change_note`,
`based_on_version` (prior version ID or null), and `latest_review` (record or
null). Catalog versions preserve their snapshot/hash; `latest_review` is a
current projection of append-only review history, not a rewrite of the snapshot.

`POST /api/case-versions` accepts exactly `request_id`, `based_on_version_id`,
`version`, `editor_code`, `change_note`, and `snapshot`; returns `{version,
duplicate}`. `snapshot` follows the synthetic fixture contract above, with
`snapshot.version` equal to `version`. The case/family identity cannot change,
the version label must be unused for that case, and the base must be its latest
version. A new revision has no review and remains demo/ineligible. Existing
presentations, responses, assignments, and family mappings keep prior versions.

A family has `family_id`, `title`, `factor_label`, `base_version_id`,
`variant_version_id`, `held_constant`, and `changed_fact`. `changed_fact` contains
`label`, `base_value`, and `variant_value`. Each original pair differs in that
single structured fact only, apart from identity/title/provenance. Narrative,
setting, and every other clinical fact are held constant. Family definitions
pin the original compared versions and are included in export.

## Local case reviews

`POST /api/case-reviews` accepts exactly `request_id`, `version_id`,
`reviewer_code`, `reviewed_on`, `comments`, `disposition`, and
`supersedes_review_id`; returns `{review, duplicate}`. `reviewed_on` is a valid
YYYY-MM-DD date no later than today. `disposition` is `approved`,
`needs_revision`, or `rejected`. The first review uses null for
`supersedes_review_id`; a subsequent review must name the latest review of the
same exact version. There is no delete or overwrite endpoint.

The stored review retains those fields and adds `review_id` and `recorded_at`
(server UTC). Reviewer code follows the physician-code syntax. Review date and
comments describe the reviewer's recorded judgment; they do not verify identity
or grant study eligibility. A later review never changes a response's pinned
review ID, review status, case snapshot, or content hash.

## Versioned collection rules and assignments

`GET /api/collection` returns `{current, history, assignments, readiness,
backups}`. `current` is the latest saved protocol or null; `history` retains all
saved versions in order. `readiness` includes `missing_fields`,
`unapproved_assignment_ids`, `configuration_complete`, and
`study_collection_enabled: false`. Configuration requires filled governance
fields, at least one current-protocol assignment, and an approved local review
for every assigned version in that protocol.
This check describes draft completeness, never study authorization.

`POST /api/protocols` accepts exactly `request_id`, `based_on_protocol_id`,
`title`, `owner_code`, `physician_codes`, `consent_statement`, `consent_version`,
`retention_days`, `backup_owner_code`, `backup_frequency`,
`backup_retention_days`, and `notes`; returns `{protocol, duplicate}`. The first
version names no prior protocol; later versions must name the latest one.
Title is required. Blank governance strings, empty code lists, and null day
counts are valid incomplete drafts. Filled day counts must be integers from 1
through 3650 (booleans and fractions are invalid). `physician_codes` is a unique
list of codes following the same ASCII code rule as physician responses.

`backup_frequency` is `manual_before_changes`, `daily_when_collecting`, or
`weekly_when_collecting`; it records a plan and does not create a scheduler.
The server adds `protocol_id`, `created_at`, `protocol_schema_version: "1.0"`,
`collection_purpose: "demo"`, `study_collection_enabled: false`,
`assignment_strategy: "manual_version_pinned"`, and `physician_code_rule`
(1–40 ASCII letters, digits, underscores or hyphens; case-sensitive).
The consent statement/version is configuration, not participant consent evidence.
Retention settings do not automatically delete any record or backup.

`POST /api/assignments` accepts exactly `request_id`, `protocol_id`,
`physician_code`, `version_id`, and `notes`; returns `{assignment, duplicate}`.
Both referenced records must exist and the physician code must be listed in
that protocol. New assignments use the latest protocol; a duplicate exact
code/version assignment under that protocol conflicts unless retrying its
original request ID. Stored records add `assignment_id` and `created_at`. An assignment
pins its exact protocol and case version even when newer versions are saved.
It is a manual demo plan, not randomization, enrollment, consent, or study use.

## Verified local backups

`POST /api/backups` accepts only `{request_id}` and returns `{backup, duplicate}`.
It uses SQLite's online backup interface, verifies integrity, and writes beneath
the configured external data directory's `backups/` folder. The client cannot
choose a filesystem path. Records contain `backup_id`, `created_at`, `filename`,
`sha256`, and `size_bytes`. Repeating the same request returns the same record.
The backup contains committed records before its own completion manifest is
inserted into `local_backups`. See README for an offline copy/verification
procedure that refuses to replace an existing destination.

## Mutation and migration guarantees

All new mutations require a canonical UUID `request_id`. An identical retry
returns the existing saved record and `duplicate: true`; a changed request
under the same ID conflicts. Stale review/version/protocol edits conflict even
when request IDs differ. Commits occur before success responses. Concurrent
requests cannot fork a revision chain. Unknown input keys remain rejected,
including forged study-purpose or study-enable fields.

SQLite database `user_version` 1 migrates to 2 in place while preserving the
original response and presentation JSON payloads. Initialization is repeatable;
unsupported database versions are rejected. Appended records and database
triggers protect history through the application; direct filesystem access
still permits tampering, and SHA-256 hashes are not a signature or trust anchor.

## Historical v1.1 presentations and saved responses

`POST /api/presentations` accepts exactly one selector: `{case_id}` for the
latest catalog version, `{version_id}` for an exact version, `{assignment_id}`
for a planned demo assignment, or `{supersedes_response_id}` for a correction.
The original presentation fields remain; v1.1 also pins catalog review/version
and planning references. An assigned response must use the assignment's
normalized physician code. Corrections keep original presentation content,
physician code, and planning references even if rules or review status change.

New saved responses have `response_schema_version: "1.1"` and all legacy
response fields plus `case_version_id`, `case_review_id`, `assignment_id`, and
`protocol_id` (nullable). Review status records the disposition at presentation
time or `unreviewed`. References unavailable on legacy records remain null in
new corrections; the original v1.0 record gains no inferred metadata. Every new
response retains `ai_advice_shown: false`, `collection_purpose: "demo"`, and
`eligible_for_study: false` regardless of the local review disposition.

## Historical v1.1 export envelope

The current export retains `exported_at`, `application`, `synthetic_only: true`,
`response_count`, and `responses`, sets `export_schema_version: "1.1"`, and adds
`case_versions`, `case_reviews`, `case_families`, `collection_protocols`, and
`assignments`. `responses` includes complete unchanged originals and every
correction, with each record's own response-schema version. Export contains
full case snapshots and protocol history so pinned observations remain
interpretable; it is a review format, not an import or restoration endpoint.
Runtime exports, reviews, protocols, assignments, and backup files stay out of Git.

# Twin Lab data contract v1.2

The [governance/lifecycle contract](milestone-3.md) defines the current additions.
New presentations require explicit capture mode, permission reference and QA
acknowledgment. New responses add governance/permission references under schema
1.2; existing saved payloads retain their original schema and values. SQLite
versions 1/2/3 migrate to 4. General managed export is 1.2, excludes restricted
response chains and private governance/permission documents, and adds its copy
manifest. The sections below retain the earlier contracts as historical context;
where they differ, milestone 3 governs current behavior.

## Current version 2 governance and plan contracts

The version markers below select strict input contracts. An omitted marker
selects the original version 1 request; an explicit `"1.0"` or unknown marker is
not a legacy request and is rejected. Unknown keys remain errors. Stored
records always include their own schema version. No historical JSON payload or
request body is rewritten, and no missing field is inferred from notes.

`POST /api/governance` version 2 retains the version 1 fields from
`governance_schema.py` and adds:

- `governance_schema_version: "2.0"`;
- `operator.professional_role` and `operator.pilot_start_date` alongside existing
  operator identity/contacts and `pilot_close_date`;
- `session: {description, max_distinct_case_versions}`; the limit is an integer
  1–200, or null for an incomplete draft;
- `retention.calendar_year_basis`, either null or
  `{pilot_close_date, anniversary_date}` using exact YYYY-MM-DD dates.

Dates may be empty in drafts. Filled start/close dates require start <= close.
The window includes 00:00 UTC on start and excludes 00:00 UTC after close.
Approval may precede the start but capture cannot. For approval, the basis must
match the close date and the following year's same month/day; February 29 permits
an explicitly chosen February 28 or March 1. Both `permission_after_close_days`
and `audit_after_close_days` must equal that interval. A close in year 9999 is
invalid because it has no supported following anniversary. Other draft values
may remain incomplete without granting authorization.

Every new approved version 2 revision requires a notice version unused by any
previously approved revision, because its new Governance ID defines a new
distinct-version allowance. Exact historical retries return the saved record
without changing the current revision. New version 1 governance writes are
rejected after version 2 cutover.

`POST /api/protocols` version 2 accepts exactly `protocol_schema_version: "2.0"`,
`request_id`, `based_on_protocol_id`, `title`, `owner_code`, `physician_codes`,
`governance_id`, `backup_owner_code`, `backup_frequency`, and `notes`. The pin
must reference an existing Governance revision. There are no version 1 consent
or retention fields in this contract. Stored records retain the common protocol
metadata described below. New version 1 writes are rejected once a version 2
plan is current, including attempts naming the current parent; identical
historical retries still return the original without making it current.

A draft governance pin is valid for planning. Human capture under a version 2
plan requires that pin to equal current approved governance. Current version 2
governance requires a linked version 2 plan; an unlinked legacy plan cannot
bypass its scope. Legacy governance may be explicitly linked, without inventing
start/session fields or a case-set limit. Permission recording, presentation and
response save/retry recheck current authorization. Version 2 permission retries
also recheck current governance, plan link, time window and withdrawal. Historical
receipt downloads remain available.

Version 2 permission receipts use `permission_schema_version: "2.0"` and retain
the existing exact notice/hash/code/choice/timestamp fields plus `session`,
`professional_role`, and `pilot_window: {pilot_start_date, pilot_close_date}`.
These private documents and new free text remain excluded from general export.
Response and general export schemas remain `1.2`; exported version 2 protocols
include only their planning fields and Governance pin.

Assignment allowance counts distinct `version_id` values for a physician code
across all protocols pinned to the same Governance ID. Rejected assignments
append nothing. Reassignment of an existing version under a new current plan,
repeat responses and linked corrections consume no additional distinct-version
slot. A new Governance scope requires a new notice version and permission.
Historical assignments and corrections retain their original references and
remain subject to current authorization; they are not automatically rebound.

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

## Collection overview, historical version 1 rules and assignments

`GET /api/collection` returns `{current, history, assignments, readiness,
backups}`. `current` is the latest saved protocol or null; `history` retains all
saved versions in order. `readiness` includes `missing_fields`,
`unapproved_assignment_ids`, `configuration_complete`, and
`study_collection_enabled: false`. Configuration requires filled governance
fields, at least one current-protocol assignment, and an approved local review
for every assigned version in that protocol.
This check describes draft completeness, never study authorization.
`governance_pin_current` is null for a legacy plan under legacy governance,
false for an outdated/missing required link, or true for a current version 2 pin.
Linked-plan missing fields also describe missing requirements of pinned
Governance. A true pin alone does not mean approval or permission.

The legacy `POST /api/protocols` request accepts exactly `request_id`, `based_on_protocol_id`,
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

SQLite database `user_version` 1 originally migrated to 2, then 3. The current
coordinator supports empty/1/2/3/4 databases and advances to 4 without rewriting
historical payload/request bytes. Initialization is repeatable; unsupported
versions are rejected before writes. All DDL and fixture seeding share an
explicit SQLite transaction; the external journals have separate durable
boundaries. Appended records and database
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

# Local case review and collection planning

User-authorized extension after v0.1: reviewer code/date/comments/disposition,
preserved case versions, matched case families, and collection rules covering
physician codes, assignments, consent, retention, and backups.

This iteration remains single-user, local, synthetic, and **demo-only**. A case
approval is a recorded reviewer judgment, not study authorization. No consent,
retention period, owner, or study approval is inferred. Actual study collection
has no enabling endpoint or switch.

## Implementation contract

All writes use the existing same-origin JSON interface and `X-Twin-Lab: 1`.
New mutations carry `request_id` (UUID); identical retries return the saved
record, changed retries conflict. Database migration must preserve old records.

### Case lab

- `GET /api/catalog` -> `{versions, reviews, families}`. A version has
  `version_id`, `case_id`, `case_version`, `snapshot`, `snapshot_sha256`,
  `created_at`, `editor_code`, `change_note`, `based_on_version`, and
  `latest_review` (record or null). Versions and reviews are append-only.
- A review has `review_id`, `request_id`, `version_id`, `reviewer_code`,
  `reviewed_on` (YYYY-MM-DD; no future date), `recorded_at`, `comments`,
  `disposition` (`approved`, `needs_revision`, `rejected`), and
  `supersedes_review_id` (previous review of this version or null).
- `POST /api/case-reviews`: `{request_id, version_id, reviewer_code, reviewed_on,
  comments, disposition, supersedes_review_id}` -> `{review, duplicate}`.
- `POST /api/case-versions`: `{request_id, based_on_version_id, version,
  editor_code, change_note, snapshot}` -> `{version, duplicate}`. `snapshot`
  follows the existing case schema. Identity/family cannot change; version must
  be new; source flags reset to unreviewed/demo/ineligible. This creates a new
  revision of the latest case version; no prior clinical content is overwritten.
- Families have `family_id`, `title`, `factor_label`, `base_version_id`,
  `variant_version_id`, `held_constant`, and `changed_fact`. All five existing
  cases receive one newly authored variant differing in the declared fact only
  (apart from case identity/title/provenance). This demonstrates matching, not
  clinical validity or a validated experimental design.
- `GET /api/cases` returns latest versions for capture (now ten cases), with
  visible review status from the latest review. Exact prior-version snapshots
  remain accessible in the catalog. Capture never shows family comparison hints.
- `POST /api/presentations` additionally accepts `{version_id}` for an explicit
  catalog version or `{assignment_id}` for a planned demo assignment. The existing
  `{case_id}` and `{supersedes_response_id}` interfaces continue to work.

### Collection plan

- `GET /api/collection` -> `{current, history, assignments, readiness, backups}`.
  `current` is the newest saved protocol or null; history preserves all versions.
- `POST /api/protocols`: `{request_id, based_on_protocol_id, title, owner_code,
  physician_codes, consent_statement, consent_version, retention_days,
  backup_owner_code, backup_frequency, backup_retention_days, notes}`
  -> `{protocol, duplicate}`. Blank governance fields / null day counts are
  permitted only as explicitly incomplete drafts. Title is required. Codes
  follow the existing ASCII code rule. `physician_codes` is a unique list of
  codes. Day counts, when set, are integers from 1 to 3650.
- `backup_frequency` is `manual_before_changes`, `daily_when_collecting`, or
  `weekly_when_collecting`. Scheduling is a recorded plan, not an automatic job.
- Server adds `protocol_id`, `created_at`, `protocol_schema_version: "1.0"`,
  `collection_purpose: "demo"`, `study_collection_enabled: false`,
  `assignment_strategy: "manual_version_pinned"`, and the fixed code rule.
- `POST /api/assignments`: `{request_id, protocol_id, physician_code, version_id,
  notes}` -> `{assignment, duplicate}`. Code must be listed in that protocol;
  assignment pins its protocol and exact case version. Records carry
  `assignment_id`, `created_at`, and the supplied fields. They are plans for demo
  use, not enrollment, consent, randomization, or permission for study use.
- Readiness lists missing governance fields and unapproved assigned versions.
  Even a complete plan has `study_collection_enabled: false`.
- `POST /api/backups`: `{request_id}` -> `{backup, duplicate}`. Creates a verified
  SQLite online backup under the external data directory's `backups/` folder.
  A backup has `backup_id`, `created_at`, `filename`, `sha256`, `size_bytes`.
  No arbitrary filesystem path is accepted. Restore uses a documented offline
  procedure to a new file; no live-data replacement endpoint is added.

### Response compatibility

Existing response objects remain unchanged. New responses retain their existing
fields and additionally pin `case_version_id`, `case_review_id`, `assignment_id`,
and `protocol_id` (nullable), under response schema `1.1`. Study eligibility stays
false. Corrections retain the original snapshot and planning references.

The export envelope is version `1.1` with complete responses plus `case_versions`,
`case_reviews`, `case_families`, `collection_protocols`, and `assignments`. Original
responses retain their original response-schema versions. All runtime reviews,
protocols, assignments, backups, and exports stay out of Git.

## Acceptance

- Version-bound reviews and revised cases survive restart without changing old
  responses. Conflicting or retried writes cannot overwrite/fork history.
- Each matched pair changes exactly its declared fact; other clinical facts and
  narrative are identical. All new content remains unreviewed and ineligible.
- Protocol edits preserve prior rules; assignments pin existing versions/codes.
- Missing consent/retention/owner values remain visible as incomplete. No study
  response can be collected by supplying a forged flag or request field.
- Backups pass SQLite integrity checks and restore into a separate temporary
  database with matching content. Existing v1 databases migrate without loss.
- UI exposes Case lab and Collection plan, with accessible dark/light styling,
  explicit errors, revision history, and the synthetic prototype notice.

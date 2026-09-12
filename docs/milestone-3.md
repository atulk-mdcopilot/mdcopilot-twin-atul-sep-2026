# Local governance, permission and response lifecycle

The user initially authorized incorporating the supplied governance documents
as draft requirements and implementing permission and lifecycle controls. The
subsequent explicit instruction to incorporate the documents as approved is
recorded at `2026-09-10T23:33:19Z`, by `project_user`, with source
`explicit_user_instruction` and scope `demo_governance_documents`. Revision 0.2
adopts the demo documents and policy values as project-approved choices. This
extension supersedes the capture and export contracts in milestone 2 where stated below.
Document approval does not appoint anyone, complete the operational governance
record, create participant permission, or authorize research, training, patient
information, cloud services or deployment.

## Reference documents and decisions

[Governance samples](governance/governance-samples-v0.1.md) is the canonical
repository adaptation of the two identical supplied Markdown files. “Synthetic”
replaces “fictional”; the pending session limit is distinguished from the ten
case identities in five matched families. Review every case version actually
assigned. The [JSON companion](governance/twin-governance.example.json) records
approved document revision 0.2 while retaining its original schema identifier.
It is not a complete operational governance record. Its demo periods are approved
project policy choices; illustrative codes are not actual assignments. Original
Downloads files and the historical fact that v0.1 was unapproved are preserved.

The operator must supply the purpose/session wording, contacts, pilot closure
date, responsible people and accepted roles, privacy/review determination,
completed permission text/version and operational evidence. Approved demo policy
values can be incorporated into the operational form without inventing them.
The approved one-year permission/audit periods mean a calendar year after pilot
closure. Because the current form takes whole days, leave those fields unset
until the close date is known and the calendar-year conversion, including leap
year handling, has been reviewed. Real contacts,
appointments and receipts are private runtime records outside Git. The source
documents retain proposed roles and unresolved operational placeholders. Six
local demo roles are supported; the future methods/research role remains deferred.

## Governance and participant permission

- `GET /api/governance` returns current governance, immutable history, receipts,
  readiness and `reference_documents` containing the approved policy and file
  metadata with SHA-256/download URLs. `GET /api/governance-documents/json` and
  `/api/governance-documents/markdown` download the approved repository documents.
  This document status is separate from operating readiness. A fresh database
  contains no operational governance or participant permission records.
- The Governance screen labels this distinction **Governance documents approved**
  and **Local operating record**. For a new record, the form fills the six approved
  response/closure/withdrawal/export/backup day values and notice/policy version
  labels, without saving automatically. It leaves actual notice text, operator
  details, accepted appointments, controls evidence and calendar-year conversions
  incomplete, and preserves previously saved operational values.
- `POST /api/governance` accepts the exact contract in
  `twin_lab/governance_schema.py`. Drafts permit absent fields. Approval requires
  complete operator/notice/retention fields, accepted role records, an accepted
  actor's dated controls attestation, and the privacy owner's approval code and
  review determination. Revisions must identify the current version. Draft or
  revoked current versions close the human capture gate; a closed pilot does too.
- These are explicit local attestations, not identity verification, legal
  determinations, independent control testing, or electronic signatures. The
  prototype remains single-user; codes provide no authentication or access roles.
- `POST /api/permissions` accepts `{request_id, governance_id, physician_code,
  choice}`. Choice is explicitly `agree` or `decline`, never preselected. The
  current approved notice and a code listed in the current plan are required.
  Receipts preserve exact notice text/version/SHA-256, code, choice and server UTC
  time. A changed notice requires a new document version and new permission.
- `GET /api/permissions/<receipt UUID>` downloads the participant's exact copy.
  This is a local custodian workflow, not a participant portal or identity check.
  A decline records no response and invalidates earlier agreement for new capture.

The approval form requires evidence for device encryption/access, absence of
external network/analytics services, lifecycle procedures, backup/restore and
control of downloaded copies. The software records these assertions; it cannot
verify the Mac's encryption or who can use the device. Never make assertions
solely because automated tests passed. Complete operational review of the actual
notice before accepting physician responses.

## Capture and compatibility

`POST /api/presentations` now requires exactly one existing selector plus
`capture_mode`, `permission_receipt_id` and `qa_acknowledged`:

- `fabricated_qa`: receipt must be null and acknowledgment must be true. The UI
  resets the checkbox for each presentation. This is a provenance assertion; no
  software can infer whether a person actually fabricated their text.
- `physician_demo`: acknowledgment is false, and the current agreed permission
  receipt must match a current-plan assignment and an approved exact case version.
  Permission, code, case approval and lifecycle restrictions are checked again
  at submission, not just when opening the case.
- `legacy_unclassified`: allowed only for an explicit correction of an existing
  historical response with that status. No permission or QA status is invented.
  Corrections preserve code, case snapshot, planning references and provenance.

Old unsaved presentations must be reopened; old saved payloads are never
rewritten. Database versions 1/2 migrate to 3, preserving original payload bytes.
New response schema `1.2` adds capture mode, governance/permission identifiers,
permission version/hash and explicit false training/research/public-release
flags. Existing response schemas remain unchanged. New policy never silently
extends, shortens or invents a historical response's retention period.

## Expiry, withdrawal and holds

For a new permission-bound original response, lifecycle metadata freezes its
original submission anchor and approved policy. Expiry is the earlier of
original submission plus response days or pilot closure plus after-close days.
The closure date means end of that UTC date. Corrections inherit the original
chain's anchor; exports, backups and policy revisions never restart it.

Ordinary review/export and further corrections exclude restricted chains.
`GET /api/lifecycle` provides content-free metadata, restrictions, copy inventory,
withdrawals and holds. Historical records without policy remain visibly unknown
and are never automatically scheduled for disposal.

- `POST /api/withdrawals`: `{request_id, physician_code, actor_code}` records
  receipt and stops use/capture for that code immediately. A code alone is not
  sufficient verification for disposal.
- `POST /api/withdrawal-verifications`: `{request_id, withdrawal_id, actor_code,
  verification_attested, withdrawal_days}` records reasonable verification. Known
  policy uses its frozen withdrawal period; legacy records require an explicit
  chosen period. Earlier existing expiry still governs. This records an actor's
  verification, not an automated identity check.
- `POST /api/holds`: `{request_id, response_ids, actor_code, authority_record}`
  scopes a hold to explicit chains. Holds prevent ordinary use and disposal.
- `POST /api/hold-releases`: `{request_id, hold_id, actor_code, authority_record}`
  records explicit release without erasing hold history.

No HTTP route deletes observations. The separate offline maintenance tool
previews eligible full chains and managed copies, requires an exact confirmation
digest and actor code, then rechecks the plan under a database write lock.
Deletion journals are flushed before destructive changes. Ordinary SQL update
and delete guards remain in place outside that narrow process. Original records
remain intact until an explicitly authorized disposal operation; this is not a
promise of forensic erasure from the filesystem or device.

## Exports, backups and restoration

General response export is schema `1.2`; it excludes private governance owner
registries and permission documents. Response objects retain their own original
schemas. Export only includes chains currently available for ordinary use.
`GET /api/export` creates a managed local copy and content-free manifest, with
source identifiers and the earliest applicable source/copy expiry. The browser's
download is an additional copy: the operator must inventory and remove it under
their documented process. The application cannot recall arbitrary copies.

Backups preserve source retention deadlines instead of rejuvenating old records.
Old backups/exports lacking manifests or policy need explicit operator review.
Backups are not encrypted by the application; verify device/storage controls.
Expiry restrictions apply when reading; physical disposal is explicit offline
maintenance, not an automatic background job.

Restoration requires a new destination, integrity checks and the authoritative
external lifecycle journals. Keep those journals outside SQLite snapshots and
retain them with the controlled backup set. A restore must reapply current
withdrawals/holds and deletion records before any restored answers are available.
It must never replace the live database automatically. See README for commands.
Every restored copy also requires fresh local governance approval and new
participant permission before human capture, protecting against approvals or
choices that changed after the snapshot. Historical approval/receipt records
remain intact for review; fabricated QA can still be used for restore testing.

Minimal permission/audit records have separately approved calendar-year policies.
The lifecycle screen reports administrative records needing review; preserving
deletion restrictions until old copies are retired takes precedence over silently
discarding the journals. Administrative record review/disposal and unmanaged
download cleanup remain operator procedures, not claims of automated compliance.
Do not offer a notice promising an unsupported automated control.

## Acceptance and exclusions

Tests must cover explicit QA acknowledgment, empty/incomplete human gates,
exact permission receipts and choices, stale/revoked permission, pinned approved
assignments, immutable migrations/corrections, original-chain expiry, immediate
withdrawal restriction, verification deadlines, scoped holds, stale-plan
rejection, copy inventory/expiry, and restoration without resurrecting restricted
or disposed responses. All test records are fabricated in temporary directories.

No test or migration approves the operational governance record, changes existing response values,
deletes current local responses, or grants study eligibility. No AI/model work,
patient data, external services, cloud backup, EHR access, push or deployment is
part of this extension.

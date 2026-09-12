# Architecture decisions and open questions

## Standalone standard-library application

No pre-existing application stack was present. Twin Lab uses Python 3.12's
standard library for a small local HTTP server, input validation, hashing, JSON,
and SQLite, plus static HTML, CSS, and JavaScript. No pip or npm packages are
required. A Docker runtime pinned by digest is recorded in `compose.yaml` and
`dependency-lock.json`; application code and tests run in the container.

This keeps the local workflow runnable without an external database,
build step, or account. Python documents SQLite as a lightweight disk-based
database without a separate server process in its
[sqlite3 documentation](https://docs.python.org/3.12/library/sqlite3.html).
The [http.server documentation](https://docs.python.org/3.12/library/http.server.html)
warns that it is not recommended for production. This implementation is confined
to the local prototype scope; it is not a deployment architecture.

The Compose service publishes a loopback host port and mounts a data directory
outside the checkout. Runtime configuration follows the official
[Compose services reference](https://docs.docker.com/reference/compose-file/services/).
See the README for exact commands and storage paths.

## Durable presentation and response records

The server persists each presentation before returning its full case snapshot.
Its UTC presentation timestamp means the server issued the case; it does not
prove that a physician saw or attended to it. The browser presents the full
snapshot, and responses retain the immutable snapshot plus its SHA-256 hash.
This preserves what was supplied even if a fixture changes later.

The server validates the exact input contract and commits a response before
acknowledging success. The original submitted strings and nulls are preserved;
trimmed values are separate. Required strings must contain non-whitespace text.
Optional confidence uses low/moderate/high labels and is self-reported decision
confidence. No disease-probability interpretation is supported.

A presentation ID is the idempotency key. An identical retry returns the same
response; changed values for that presentation are rejected. An explicit
correction creates a new presentation of the original saved snapshot and a new
response linked by `supersedes_response_id`. Only the latest revision can be
corrected, and its normalized physician code must match. The original is never
silently overwritten. This is an application policy, not tamper-proof storage.

The JSON export includes available originals and corrections under a versioned
envelope. Export timestamps vary by download; saved observations do not. The
full case, HTTP, response, and export contracts are in [schema.md](schema.md).

## Synthetic data and local trust

The five original fixtures are authored placeholders, each from a separate
provisional case family. Five additional variants now form explicit matched
pairs. Source fixtures have no clinical-review approval or study eligibility. There
are no hidden clinical labels or outcomes. A strict allowlist rejects unknown
fixture and request fields to reduce accidental inclusion of additional data.

Physician code is the only requested participant identity label. Private
governance separately records accepted responsible people and operator contacts.
No credentials are needed;
there is no authentication or per-code privacy boundary. The interface is for
a single trusted local user. Same-origin writes and a required custom request
header reduce unintended browser writes; they do not provide authentication.
SQLite is not encrypted. Anyone with filesystem access can read or alter it.

The default data directory is `${HOME}/.local/share/twin-lab`, outside Git.
Exports must also be saved outside the checkout. Git ignore rules provide
additional safeguards against common data/credential filenames, but cannot
recognize sensitive content copied into an arbitrarily named source file.
Never force-add runtime data, response exports, logs containing response text,
or credentials. No external analytics, assets, or model services are required.

## Immutable catalog, review history, and matching

Case content now lives in an append-only SQLite catalog initialized from the
synthetic source fixtures. A version has a fixed snapshot/hash, identity,
provenance, editor metadata, and optional parent version. Reviews are separate
records pinned to an exact version; a later review names the one it supersedes.
A case edit produces a new version that must receive its own review. Source
fixtures stay unreviewed and ineligible; catalog review projections may show a
local disposition without changing those source files or granting study use.

Review/version/protocol mutations use UUID request IDs for retry recovery.
Transactions reject stale parent references and changed retries, preserving one
revision chain under concurrent use. New responses pin the catalog version,
review, assignment, and protocol available at presentation time. Corrections keep
that context. Database schema 2 migrates legacy records without rewriting their
payloads; legacy response objects retain response-schema 1.0 inside export 1.1.

Matched families vary one declared structured fact while retaining narrative,
setting, and all other clinical facts. Comparison metadata appears only in Case
lab, avoiding a family-change hint in unaided capture. Family definitions pin
their original versions. New case revisions are not automatically promoted into
the original match. Selected variations are authoring examples that require
clinical and design review, not validated experimental manipulations.

## Draft collection rules and verified local backups

Rules are versioned local records, and assignments manually bind a listed code
to an exact case version and protocol. This makes assignment and response
context inspectable without introducing accounts, randomization, or a service.
Code normalization follows the response contract; codes are labels, not identity
verification. Readiness exposes missing governance fields and unapproved assigned
versions. A complete configuration still cannot enable study collection.

The incorporated demo governance documents and policy choices have project-user
approval recorded at 2026-09-10T23:33:19Z. Earlier v0.1 source/adaptation status
was draft/unapproved; revision 0.2 preserves that history and records the new
explicit approval. The application still permits incomplete operational drafts.
Collection-plan wording is still planning text; exact participant permission now has a separate
versioned receipt and capture gate. Frequency fields do not schedule backup
jobs, and physical disposal requires an explicit offline operation.

Manual backups use SQLite's online backup interface, verify the result, and stay
under the external data directory. Digest and size support checking the saved
artifact; they do not provide tamper-proofing or off-machine redundancy. Backup
completion metadata is written after the snapshot, so a backup omits its own
manifest row. The documented restore procedure creates a separate file and
local review instance rather than overwriting live data. Backups, protocols,
reviewer records, assignments, and exports are runtime data and excluded from Git.

## Governance and lifecycle boundaries

See [milestone 3](milestone-3.md). New capture records distinguish explicitly
fabricated QA from a physician's permitted demo response. Legacy observations
remain unclassified and unchanged. Permission is rechecked when presenting,
saving and retrying a human response; study/training/public-release flags stay
false. Contacts and permission documents are omitted from general response export.

Retention freezes the original response's approved policy. Corrections reuse its
anchor. Restrictions remove expired/withdrawn/held chains from ordinary use,
while physical disposal is a separate preview-and-confirm operation. The narrow
disposal transaction temporarily suspends DELETE guards and restores them;
capture/review have no overwrite/delete path.

Two external append-only journals preserve deletion and withdrawal/hold evidence
across old SQLite snapshots. They are flushed before destructive/restrictive
operations; absent or malformed journals fail closed. Restore creates a new
sanitized file and copies authoritative journals, never overwriting live data.
A restoration barrier also requires fresh governance approval and new permission
before human capture, because an older snapshot may contain obsolete approvals.

No code verifies a human's identity, authority, device encryption or claims in a
controls attestation. Administrative record retirement and downloaded-copy
cleanup require documented operator procedures. The readiness indicator means
that required local assertions are recorded, not that legal compliance has been
independently established. Project-user approval of the incorporated documents
does not create an approved operational record or participant agreement.

## Approved demo documents and remaining operational decisions

The approval record uses `approved_by: project_user`,
`source: explicit_user_instruction`, `scope: demo_governance_documents`, and
`recorded_at: 2026-09-10T23:33:19Z`. It does not identify a natural person or claim
a clinical/privacy role. The canonical Markdown and JSON carry document revision
0.2; the JSON keeps its existing schema identifier and filename for continuity.
The source Downloads files remain unchanged.

Demo retention/withdrawal values are approved project policy choices, not legal
minimums. One-year permission/audit periods are calendar-year policies; the
application's day-based fields remain unset until the pilot close date and a
reviewed conversion are available. No calendar year is silently treated as 365
days. Role proposals and missing contacts remain unresolved, and the participant
notice is not yet ready to offer. Its completed local version, required review,
accepted appointments, device/control evidence and explicit participant choice
remain distinct from document approval. Future research wording and its periods
remain deferred drafts. Existing responses acquire no permission, classification,
retention rule or changed expiry through this document update.

## Assumptions and unresolved questions

- Clinical reviewers still need to review plausibility, wording, information
  completeness, and whether the cases elicit useful unaided decisions.
- The five declared matched pairs do not constitute a validated experimental
  design. Clinical reviewers still need to assess the selected factor changes.
- The confidence labels, required fields, and single-user flow are prototype
  choices. User testing should decide whether they need revision.
- Future studies need separate consent, identity, access, retention, deletion,
  and governance decisions. This prototype is not approval to collect patient
  information or conduct a study.
- Migration and stale-write handling now cover this local extension. Actual
  multi-user identity/access control, backup automation, administrative retention,
  study collection, and future MDcopilot interfaces require separate scope.
- A local export permits manual review; it does not establish data integrity,
  clinical accuracy, representativeness, or a learned physician twin.

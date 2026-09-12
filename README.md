# Twin-Atul-Sept-2026
https://chatgpt.com/share/6a9f4e68-faf0-83ea-9362-e2e645bee8f9

Twin Lab is a **synthetic-case prototype, not a validated clinical tool**.
It presents ten newly authored adult GI-bleeding demo cases: the five original
cases and one matched variant of each. Local case reviews, immutable revisions,
and draft collection rules extend the original unaided-response workflow.
All source cases are **unreviewed and ineligible for study**; local approval
records never enable study collection. The discussion link above is background.
Current starter cases use wording revision 1.1, which removes “fictional” from
the narrative and facts. The synthetic label remains visible and exact data
provenance appears at the bottom of each case. Original 1.0 versions remain in
history; existing local case revisions and saved observations are preserved.
The [first-build brief](MDcopilot_Twin_First_Build.md) and
[case/collection extension](docs/milestone-2.md) and
[governance/lifecycle contract](docs/milestone-3.md) define the implemented scope.

The [quality implementation plan](docs/quality-plan.md) proposes the next five
engineering phases, their acceptance checks, and the seven quality rules.
It is a plan; its tooling and behavior changes are not implemented yet.

## Setup and start

Install and start Docker with the Docker Compose plugin. No Python, Node, pip,
npm packages, accounts, credentials, or cloud service are required on the host.
The application uses Python's standard library and SQLite. `compose.yaml` pins
the container runtime by digest; `dependency-lock.json` records the runtime and
the absence of third-party application dependencies. The first run requires
access to pull that runtime image. Subsequent runs with the image cached need
no network service for application operation.

From this repository directory, run:

```sh
docker compose up -d
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765).
The published port is bound to loopback for use on this machine. Do not change
the binding to expose the prototype on a shared or public network.

Use **Dark mode** in the header to switch between dark and light appearance.
Until you choose a theme, Twin Lab follows your system appearance. Your choice
persists in this browser across reloads; only the theme preference is stored in
browser local storage, never response text or physician codes.

To check startup or stop the application:

```sh
docker compose ps
docker compose logs twin-lab
docker compose down
```

Application source is local; no frontend build or dependency-install command is
needed. After editing source, restart with `docker compose restart twin-lab`.

## Capture, review, correct, and export

1. Choose **Fabricated software test** and explicitly confirm that your answers
   are fabricated. Then select a case. Read its narrative, facts, version and provenance.
   Each case is explicitly synthetic and intended only for demo use. A locally
   recorded review disposition describes that exact version, not study eligibility.
2. Enter a physician code, next action, next information request, and what would
   change the decision. If appropriate, say that information is insufficient.
   Rationale is optional and can be brief; confidence is optional,
   self-reported decision confidence, not disease probability.
3. Save. A success state is shown only after the database commit succeeds.
   Repeating an unchanged save uses the same presentation ID and does not create
   an extra observation. Resolve any visible save error before assuming success.
4. Open local response review to inspect the saved values and case snapshot.
   Use its explicit correction action to append a linked revision. Originals
   remain available; only the latest revision can be corrected, with the same
   normalized physician code.
5. Export JSON from the review screen. Save the download outside this checkout,
   in a controlled local folder. Export includes available originals and
   corrections, case versions/reviews, family definitions, protocols, and
   assignments with the versioned envelope documented in [schema.md](docs/schema.md).
   Withdrawn, expired or held responses are excluded. Each export also has a
   managed copy and inventory record under the data directory. Downloaded copies
   must be tracked and removed by the operator; the app cannot recall them.

To demonstrate persistence, save a response, run the following, then open review
again and export the saved record:

```sh
docker compose down
docker compose up -d
```

The default database remains on the host at
`${HOME}/.local/share/twin-lab/twin-lab.sqlite3`, mounted into the container's
data directory. Presentations, responses, case reviews/revisions, protocols,
and assignments survive container shutdown and restart. Original values,
normalized values, exact presented case snapshots,
SHA-256 hashes, versions, server-issued UTC presentation/submission timestamps,
and correction links are retained. Presentation time records server issuance;
it is not proof that a user saw the case.

An optional command-line export, also saved outside the repository:

```sh
curl --fail --show-error http://127.0.0.1:8765/api/export \
  --output "${HOME}/Downloads/twin-lab-export.json"
```

That command replaces an existing file with the same name; use a different
filename to retain earlier exports. Exported records contain physician response
data even though the cases are synthetic. Do not commit or share them as source.

## Case lab: reviews, revisions, and matched families

Open **Case lab** to inspect the catalog, version history, and matched families.
Each family identifies the changed fact and the information held constant.
These comparisons are for case authoring/review and are not shown as decision
hints during response capture. Matching demonstrates the software workflow; it
does not establish clinical validity or an experimental design.

Select an exact case version, enter a reviewer code, review date, comments, and
disposition (**approved**, **needs revision**, or **rejected**), then save. The
review date records the reviewer's date; a separate server UTC timestamp records
when it was saved. Future dates are rejected. A subsequent review appends to the
previous review of that version. It never erases earlier judgments.

Create a case revision from the latest version with a new version label, editor
code, and change note. Its identity and family remain fixed, the prior clinical
content stays available, and the new version starts unreviewed and ineligible.
Original matched-family definitions remain pinned to their original versions;
a revised case is not automatically a reviewed replacement in that comparison.
The supplied wording revision changes no clinical values. Historical snapshots,
including original family comparisons, retain their original wording.
If another tab saved a newer review/revision, reload and inspect that history
before submitting again. The server rejects stale writes instead of forking it.

## Collection plan: demo rules and assignments

Open **Collection plan** to save versioned draft rules. Enter a plan title,
owner code, allowed physician codes, draft permission planning text and
its version, retention days, backup owner, backup frequency, and backup retention
days. Do not use names, email addresses, patient information, or credentials.
Codes contain 1–40 ASCII letters, digits, underscores, or hyphens and are
case-sensitive; they are local
labels, not accounts. Keep any identity lookup separately from this application.

The incorporated demo governance documents and policy choices are approved as
described below. Collection-plan text remains planning information; it does not
create participant permission or accepted appointments. Keep missing operational
details incomplete until they are entered locally. Day counts must be whole
numbers from 1 to 3650. Revised rules append a new protocol; previous versions
remain in local history and export.

Create an assignment using the latest saved protocol, a physician code listed in
that protocol, and an exact case version. Assignment is manual and pins those
choices. When capturing an assigned response, the physician code must match the
assignment. Later protocol or case edits do not change existing assignments or
saved responses. Readiness identifies missing rules and unapproved assigned
versions. Even a complete plan remains **demo-only**.

This planning field does not collect permission or control participation. Use
the separate Governance workflow below for exact participant permission.
Backup frequency is a recorded responsibility, not an automatic job.
There is no study-enable switch. Actual study collection needs a separately
authorized design and implementation after case/workflow review.

## Governance and physician participation

Open **Governance** to complete the local operational record. The
[incorporated demo documents](docs/governance/governance-samples-v0.1.md) and
their policy choices have explicit project-user approval, recorded at
`2026-09-10T23:33:19Z` in document revision 0.2. The
[JSON companion](docs/governance/twin-governance.example.json) records that approval.
The Governance screen shows **Governance documents approved** and offers
**Download approved policy JSON** and **Download approved governance document**.
The original Downloads files remain unchanged. Document approval does not fill
missing operator/contacts, accept a role, attest to device checks or record a
participant's agreement; these remain separate operational requirements.

Approved demo periods include the earlier of 90 days from original submission
or 30 days after pilot closure, 30-day export/backup limits, and withdrawal
disposal within 30 days after verification or earlier expiry. Permission and
audit records have a one-calendar-year period after pilot closure. Their current
application fields use days: leave them unset until the close date is known and
the appropriate calendar-year day counts are reviewed. Do not assume 365 days.

The **Local operating record** form separates operator/contacts, exact participant notice/version, retention
periods, accepted responsible people, and dated evidence of operational checks.
For a new record it fills the six approved response/closure/withdrawal/export/
backup day values and document/policy version labels. It does not save a record
automatically. Notice text, contacts, role acceptances, check evidence and the
calendar-year day counts remain incomplete; existing records keep their values.
Saving an operational draft is allowed while incomplete. Operational approval
requires the remaining decisions and attestations, including the privacy owner's
code and review determination. The project-user document approval is retained
separately and does not substitute for those records.
These records are local assertions, not verified identities or legal approval.
Never check controls or accept a role on someone else's behalf.

**Actual physician demo** remains unavailable until current approved governance
is complete. Create reviewed assignments in Collection plan, show the approved
notice, and record the participant's explicit Agree or Decline. Neither choice
is preselected. Download the exact permission receipt for the participant. An
agreed receipt is tied to the current notice, code and approved assigned case.
The server checks permission again on save. A new notice/revocation, withdrawal,
expired pilot or changed case approval can prevent capture from an old tab.

Historical answers remain unchanged and show **unverified origin/permission**.
Their corrections retain that status. Do not classify them as fabricated or
attach new permission retroactively. New fabricated tests have explicit QA
provenance. All modes remain ineligible for study and never show AI advice.

The lifecycle section records withdrawals, verification and scoped holds; it
shows original-chain expiry and copy inventory. Withdrawal stops ordinary use
immediately. Disposal requires reasonable verification or a previously approved
expiry; held chains cannot be disposed. Device encryption, real access control,
downloaded-copy cleanup and administrative receipt/audit retention remain
documented operator responsibilities. Review the actual notice against these
limits before inviting physicians.

## Local backups and a separate restore check

Use **Create local backup** in Collection plan to create a verified SQLite backup in
`${HOME}/.local/share/twin-lab/backups/`. The UI records its filename, UTC time,
SHA-256 digest, and size. It captures committed application data; its own
completion record is written afterward and is not inside that backup. Copies
remain on this machine and are not encrypted or uploaded. Follow the approved
local backup ownership/frequency; there is no automatic scheduling or deletion.

To verify a backup without altering the live database, first stop the application
with `docker compose stop twin-lab`, then replace the placeholder filename below.
Use the maintained restore tool, which requires the current external lifecycle
journals, refuses to overwrite an existing destination, checks integrity and
foreign keys, and reapplies restrictions/deletions before the copy can be used:

```sh
docker compose run --rm --no-deps twin-lab python -m twin_lab.maintenance \
  --data-dir /data restore \
  --source /data/backups/REPLACE_WITH_BACKUP_FILENAME.sqlite3 \
  --destination /data/restore-check/twin-lab.sqlite3
```

For a local review of that separate restored copy, with the normal service still
stopped, start a temporary instance using only the restore directory:

```sh
docker compose run --rm --no-deps --service-ports twin-lab python -m twin_lab.server \
  --container-bind --data-dir /data/restore-check
```

Review the copy at the same local URL, then stop that temporary instance with
Ctrl-C and restart the normal service with `docker compose up -d`. This procedure
does not replace the original database. Avoid copying a live SQLite file as a
backup; use the application's verified backup operation. Retain the authoritative
`deletion-ledger.jsonl` and `lifecycle-events.jsonl` with the controlled backup
set; restoring an old SQLite file alone is not a safe restoration procedure.

## Explicit offline disposal

No startup job or web endpoint deletes answers. To review eligibility, stop the
service and create a plan in the external data directory. Use a new filename
for each plan; an existing file is never overwritten:

```sh
docker compose stop twin-lab
docker compose run --rm --no-deps twin-lab python -m twin_lab.maintenance \
  --data-dir /data plan --output /data/twin-lab-disposal-plan.json
```

Inspect the full plan, holds, unknown-policy records and copy/administrative
review obligations. Only after explicitly approving those exact effects, apply
it with the responsible actor's actual code and the plan's confirmation digest:

```sh
docker compose run --rm --no-deps twin-lab python -m twin_lab.maintenance \
  --data-dir /data apply --plan /data/twin-lab-disposal-plan.json \
  --actor-code REPLACE_WITH_ACTOR_CODE --confirm REPLACE_WITH_PLAN_DIGEST
docker compose up -d
```

The tool rejects changed plans/state, preserves held chains and flushes deletion
records before removing full chains and eligible managed copies. This does not
erase arbitrary downloaded copies or guarantee forensic erasure. Unknown legacy
records never acquire a retention period simply because a new plan was saved.

## Tests

Run the automated test suite in Docker:

```sh
docker compose run --rm twin-lab python -m unittest discover -s tests -v
```

Run the Git exclusion check with host Git (it stages synthetic sentinels in an
isolated temporary repository and leaves this checkout's index untouched):

```sh
sh tests/check-git-ignore.sh
```

Tests use temporary databases and do not need physician data. They cover the
validated schemas, exact snapshots and values, persistence, duplicate retry,
correction history, JSON export, local HTTP protections, and Git data exclusions.
Extension tests cover immutable reviews/versions, declared matched-pair changes,
stale/concurrent writes, incomplete rules, pinned assignments, backup restoration,
and migration of original v1 response objects without rewriting them.
Governance tests cover exact permission receipts, capture gates, original-chain
expiry, withdrawal, holds, disposal and restoration without resurrecting data.
For a manual smoke test, follow the case → save → shutdown/start → review →
correction → export flow above. Inspect all screens for the synthetic prototype
notice and confirm both original and corrected records remain in the export.

## Data handling and cleanup

The five original source fixtures remain in `fixtures/cases.json`; matched
variants and family definitions live alongside them in `fixtures/`. Runtime
databases, backups, case-review records, collection plans, assignments, response
exports, logs containing response text, and credentials must remain outside Git.
The `.gitignore` adds common data/credential patterns as a second safeguard;
do not force-add ignored files or paste responses into source documents.

There is no authentication, per-physician privacy boundary, encrypted database,
or tamper-proof audit log. Physician codes are labels rather than accounts.
Local users can access the local custodian interface; there is no participant
privacy boundary. Restricted content is excluded from ordinary review/export.
Application-level
append-only behavior does not prevent direct filesystem edits. Keep this
single-user demo on a trusted machine and never enter patient information.

Do not reset the data directory to implement withdrawal or retention: that would
also destroy the journals needed to keep old backups from restoring restricted
content. Use the explicit lifecycle workflow and separately retire controlled
copies and administrative records under the approved policy.

## Scope and further work

There are no AI recommendations, diagnoses or answer keys, model training,
patient data, clinical orders, cloud services, analytics, EHR integration, or
public deployment. Software tests do not validate clinical plausibility.
The next review is of case content, the response form, and provenance.

See [scope](docs/scope.md), [architecture decisions](docs/decisions.md),
[data contract](docs/schema.md), the [ordered backlog](docs/backlog.md), and
[actual verification results](docs/verification.md).

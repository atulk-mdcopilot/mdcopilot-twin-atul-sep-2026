# Twin Lab verification

## Approved governance documents, revision 0.2 — September 10, 2026

The user's explicit approval is recorded in both incorporated documents, with
`recorded_at: 2026-09-10T23:33:19Z`, source `explicit_user_instruction`, and
scope `demo_governance_documents`. This is the time approval was recorded,
not an independently verified signature. The original attachments in Downloads
were preserved.

- **116 tests passed in 7.918 seconds**, with no failures or skips, using
  `docker compose run --rm twin-lab python -m unittest discover -s tests -q`.
  Three new tests cover approved source metadata, preserved unresolved operating
  facts and scope restrictions, exact downloadable bytes/hashes, and allowlisted
  download paths. Test databases are temporary.
- `git diff --check` passed. No dependencies were added.
- Read-only browser verification on the restarted app at `127.0.0.1:8765`
  confirmed the approved-documents panel, revision and recorded approval time,
  both download links, and the separate incomplete local operating record.
  A new unsaved form showed the approved response period of 90 days and five
  30-day periods. Permission/audit year fields remained blank with calendar-year
  guidance. No form was saved, and no browser warnings or errors were observed.
  The temporary verification tab was closed; existing user tabs were untouched.
- Read-only live checks confirmed both downloaded files match their published
  SHA-256 hashes. All original payload bytes remain unchanged: **42 presentations,
  16 responses, 20 case versions, and 5 families**. Saved reviews, collection
  protocols, and assignments remain zero. SQLite integrity and foreign-key checks
  passed. No operating records or permission receipts were created.

Approval applies to the permission template and demo retention policy. It does
not fill missing contacts, accept responsibilities for other people, supply a
pilot close date, attest completed controls, or record participant permission.
Actual physician capture therefore remains disabled until those separate facts
are completed. New forms prefill approved day values and version labels without
overwriting saved records. The approved one-calendar-year periods remain years
in the source policy rather than being silently converted to 365 days.

Files changed for this follow-up: both references in `docs/governance/`;
`twin_lab/governance.py`, `server.py`, static `governance.js`, `governance-form.js`,
and `capture-mode.js`; new `tests/test_approved_documents.py`; `AGENTS.md`,
`README.md`, and milestone-3/scope/backlog/decisions/verification documentation.
Participant receipt download filenames now use the existing Git-excluded
`twin-lab-permission-` prefix. No original response, clinical fixture, or runtime
operating record changed. Work remains local on `feat/twin-lab-v0-1`, uncommitted;
nothing was pushed or deployed.

## Governance and lifecycle extension — September 10, 2026

Implemented on the existing local branch `feat/twin-lab-v0-1`. Existing work
remains uncommitted; no commit, push or deployment occurred.

Final commands and actual results:

```sh
docker compose run --rm twin-lab python -m unittest discover -s tests -q
sh tests/check-git-ignore.sh
git diff --check
```

- **113 tests passed in 7.428 seconds**, with no failures or skips. The suite
  includes the prior 50 tests plus 63 governance, capture/HTTP, lifecycle,
  restore-barrier and maintenance-command tests. Test databases are temporary.
- **40 runtime/credential sentinels excluded** by normal staging in an isolated
  test repository. Real checkout index untouched. Both canonical draft reference
  documents remain eligible source files; no private governance is placed there.
- Whitespace check passed. No application dependencies were added.
- Review-driven regressions cover human retry after decline/revocation, missing
  journals, partial restores, later restoration of previously absent responses,
  unchanged withdrawal anchors, and exported filenames matching Git exclusions.
  The older raw-copy restore test was updated to use the journal-aware restore
  workflow; copying only SQLite now correctly fails closed.

Browser verification used a separate temporary server at `127.0.0.1:8766`:

- Fabricated QA acknowledgment is required/reset for each presentation and
  correction; saved data survives page reload. A retained requested action can
  be resumed after acknowledging, without losing the intended correction.
- Draft governance preserves exact whitespace/text/hash across save/reload;
  roles, periods and control checks remain unapproved and human capture disabled.
- Both light/dark appearance were inspected; dark preference persisted.
- Explicitly fabricated test-only approval fixtures enabled a rehearsal of
  unselected Agree/Decline, exact receipt copy, approved assignment selection,
  participant-code binding, human-demo save and permission-preserving correction.
- Withdrawal excluded original and correction from ordinary review. A pending
  stale correction was rejected with HTTP 409. Managed export appeared in the
  inventory. No browser console errors or warnings were observed.
- Temporary database verification found four fabricated test responses, two
  exact permission receipts, no stale submission and no available responses
  after the test withdrawals. The test browser tab and container were closed;
  those fixtures did not enter the real database.

Browser legacy-correction display and hold-entry/offline disposal were not
separately exercised; their server/migration/lifecycle paths have automated
coverage. Tests do not verify real identities, clinical review, legal approval,
Mac encryption, arbitrary downloaded copies, or administrative record retirement.

Before migration, a verified local SQLite backup was created at
`~/.local/share/twin-lab/backups/twin-lab-8c64d08f-5d49-4a4d-b99b-a07f20cbd988.sqlite3`.
Its SHA-256 was
`8de984588dd849984fcdde595bd1152c9e1a1c6f52368746a988118d12752827`.
A temporary copy was upgraded first; afterward the actual service was restarted
and checked through read-only queries and local HTTP. Both checks verified:

- All original payload bytes unchanged: **42 presentations, 16 responses,
  20 case versions, 5 families**, with zero saved reviews, protocols or assignments.
- Database version 3; SQLite integrity and foreign-key checks passed.
- **Zero governance versions and zero permission receipts**; actual physician
  participation and study collection remained disabled. Existing origins and
  permission remained unclassified. No original response was changed or deleted.
- The local app and new static modules returned HTTP 200 at `127.0.0.1:8765`.

Files added for this extension: `twin_lab/governance.py`,
`governance_schema.py`, `lifecycle.py`, `lifecycle_files.py`,
`lifecycle_restore.py`, `lifecycle_admin.py`, `maintenance.py`;
`twin_lab/static/governance.js`, `governance-form.js`, `capture-mode.js`,
`lifecycle.js`; `tests/test_governance.py`, `test_capture_governance.py`,
`test_restore_governance.py`, `test_lifecycle.py`, `test_maintenance.py`;
`docs/milestone-3.md` and the two canonical references in `docs/governance/`.

Integration updates: `twin_lab/store.py`, `server.py`, `schemas.py`, `backups.py`;
static `app.js`, `index.html`, `collection.js`, `review.js`, `api.js`,
`planning-ui.js`, `planning.css`; existing capture/HTTP/catalog/collection/migration
tests and helpers; Git-ignore checks; `AGENTS.md`, `.gitignore`, `README.md`, and
scope/schema/decisions/backlog/verification documentation. Clinical fixtures,
the first-build brief, runtime dependency lock and separate MDcopilot repositories
were preserved.

## Original first-build verification — September 8, 2026

Verified locally on September 8, 2026 (America/New_York), on branch
`feat/twin-lab-v0-1`. No changes were committed, pushed, or deployed. The supplied
brief was preserved; the original README title and discussion link remain.

## Automated checks

From the repository directory:

```sh
docker compose run --rm twin-lab python -m unittest discover -s tests -v
sh tests/check-git-ignore.sh
git diff --check
```

- Python suite: **22 tests passed**, no failures or skips (4.119 seconds in the
  final full backend run). Covers strict cases/values, hidden-field rejection,
  exact snapshots and versions, original versus normalized values, restart,
  concurrent duplicate saves, linked corrections, stale correction conflicts,
  JSON export, malformed requests, origin/host protections, and real SQLite
  write failure without false success or response-text logging.
- Git check: **passed**. A normal `git add .` in an isolated temporary repository
  excluded all **30** runtime/credential sentinels. Only its `.gitignore` and
  synthetic fixture file were staged; the real repository index was untouched.
- Whitespace check: passed.
- After simplifying the export button, reran
  `docker compose run --rm twin-lab python -m unittest discover -s tests -p test_http.py -v`:
  **8 HTTP tests passed** (4.096 seconds), and rechecked the browser download.
- First integration run had two missing-static-resource failures while the UI
  files were being written; these were resolved before the passing suite.

Runtime used: Docker 29.6.1, Docker Compose v5.2.0, Python 3.12.14, SQLite 3.40.1.
The image digest is locked in `compose.yaml` and `dependency-lock.json`.

## Browser and persistence smoke test

At `http://127.0.0.1:8765`:

1. Confirmed all five case choices and the persistent synthetic/unreviewed/
   ineligible/not-validated notice. Opened a case and checked the complete
   narrative, facts, case/version/family, and provenance display.
2. Confirmed empty-field rejection. Separate UI checks also rejected malformed
   physician codes and whitespace-only required text.
3. Saved an explicitly labeled software-test response, with whitespace and
   literal HTML-looking text. Review displayed the text without executing it.
4. Downloaded an HTTP export outside Git, ran `docker compose restart twin-lab`,
   downloaded again, and compared the complete saved response arrays in Python:
   **identical**. Reloaded the browser and retrieved the response in review.
5. Created an explicit correction; both records remained visible, and the new
   response linked to the unchanged original and its original case snapshot.
6. Opened another case, stopped the server with `docker compose stop -t 1 twin-lab`,
   and attempted a save. The UI displayed “Save not confirmed” and retained the
   unchanged values. After `docker compose start twin-lab`, retry saved once.
7. Used the final **Export JSON** button and observed a native browser download
   event. Independently exported with curl and verified its response objects
   exactly matched SQLite, included the original and linked correction, and had
   matching snapshot hashes. There were three software-test observations total.
8. Checked desktop and 390-pixel mobile layouts; corrected mobile grid overflow
   and verified the final page fits without horizontal page overflow.

The initial Blob-based download did not yield a browser download event. The
final implementation uses the server's native JSON attachment, whose download
event was verified. The browser control does not expose the final downloaded
file path; export byte/content checks used a separate local curl download.

Source inspection found no LLM client, patient-system integration, analytics,
external asset, cloud call, or automatic update. Runtime browser fetches use the
local API; a same-origin content policy restricts browser resource connections.
Docker's published port is `127.0.0.1:8765`. This is not an operating-system
firewall guarantee against arbitrary future outbound code.

## Limits of verification

Native unsaved-discard confirmation was not conclusively verified by the
browser-control tool; its interaction timed out. This is separate from the
verified saved-response persistence and failed-save retry behavior. Unsaved
drafts remain in browser memory and are not restored after closing the page.

Clinical plausibility, study eligibility, physician identity, tamper resistance,
multi-user use, browser compatibility beyond the tested browser, and production
operation were not validated. All fixtures remain unreviewed and study-ineligible.
Local data is not encrypted. The software-test observations and local exports
were left outside Git in `~/.local/share/twin-lab`; README documents cleanup.

## Files delivered

- Updated `README.md` with exact setup, usage, tests, storage and cleanup.
- Added `AGENTS.md`, `.gitignore`, `compose.yaml`, `dependency-lock.json`.
- Added `docs/scope.md`, `docs/decisions.md`, `docs/backlog.md`, `docs/schema.md`,
  and this verification record.
- Added `fixtures/cases.json` with five synthetic demo fixtures.
- Added `twin_lab/__init__.py`, `schemas.py`, `store.py`, and `server.py`.
- Added `twin_lab/static/index.html`, `app.js`, `snapshot.js`, `review.js`,
  and `styles.css`.
- Added `tests/helpers.py`, `test_schemas.py`, `test_store.py`, `test_http.py`,
  and `check-git-ignore.sh`.

`MDcopilot_Twin_First_Build.md` was supplied by the user and remains unmodified.

## Dark mode follow-up

Added a keyboard-accessible header toggle and complete light/dark color tokens.
The theme follows system appearance until selected, then stores only `light` or
`dark` in browser local storage. Browser checks confirmed switching by mouse and
keyboard, persistence after reload, unchanged draft text during switching, and
the appearance of capture and review screens in both themes. No new responses
were submitted. The temporary appearance-test draft was cleared.

Reran the documented Docker unittest command: **22 tests passed in 4.116 seconds**.
Changed `twin_lab/static/index.html`, `styles.css`, and `twin_lab/server.py`; added
`twin_lab/static/theme.js`; updated README and this record. No dependencies,
commits, pushes, or deployments were added.

## Local review and collection-planning extension

Verified September 9, 2026 on the same local feature branch. Final command:

```sh
docker compose run --rm twin-lab python -m unittest discover -s tests -v
```

**47 tests passed in 5.323 seconds**, with no failures or skips. Added coverage
for immutable case/review histories, five single-fact matched pairs, conflicting
and concurrent revisions, exact consent text, incomplete governance, assignment
codes/version pins, verified backup restoration, and legacy v1 migration. HTTP
tests exercise every new endpoint, duplicate results, and forged study flags.
The Git exclusion check again passed all **30 sentinels**. `git diff --check`
passed for tracked changes; the existing implementation remains uncommitted.

Browser smoke used a separate container at `http://127.0.0.1:8766`, with its
database in temporary container storage. It saved a software-test review, a
case revision, an incomplete draft protocol, a version-pinned assignment, two
demo responses, and a verified backup. API inspection confirmed the responses
retained case version 1.0 and its review after version 1.1 was added. Assigned
capture retained its physician code and planning references. Readiness continued
to list missing governance fields; study collection remained disabled. A native
JSON download event was observed and export content was independently checked.
The new Collection plan screen was inspected in light and dark appearances.
The test container was removed after verification; these review/plan records
were never written to the normal local database.

Independent backend checks also exercised concurrent backup retries alongside
presentation saves, and recovery after interruption between backup-file rename
and manifest commit. Both preserved a single backup. File and directory fsync
now precede the backup success record.

Before updating the normal service, a verified SQLite backup was saved outside
Git. After the restart completed, comparison with that backup confirmed all
**10 existing responses and 17 presentations were preserved byte-for-byte**.
The migrated database passed SQLite integrity checking, reported schema version
2, and served ten case versions and five families. No clinical reviews,
protocols, or assignments were created in the normal database by this task.
The first migration probe ran before the asynchronous restart finished; the
post-restart probe passed every assertion.

Added `catalog.py`, `catalog_schema.py`, `collection.py`, `collection_schema.py`,
and `backups.py` under `twin_lab/`; `fixtures/families.json`; and frontend
`api.js`, `lab.js`, `collection.js`, `planning-ui.js`, and `planning.css`.
Updated storage/schema/HTTP integration, capture/review/theme-aware rendering,
AGENTS, README, scope, decisions, backlog, and data-contract docs. Added
`docs/milestone-2.md`, three backend test modules, and new HTTP assertions.

This verifies the local software workflow, not clinical approval or study
readiness. Approved consent text/version, actual retention periods, and owner
codes still need to be entered; none were invented. Retention and frequency
fields record responsibilities and do not schedule deletion or backups.
Family comparisons remain pinned to their original versions. No new
dependencies, commits, pushes, deployments, or external integrations were added.

## Case wording and provenance follow-up

On September 9, 2026, removed “fictional” from the narratives and fact values of
all ten current starter cases by appending wording revision 1.1. The original
1.0 snapshots remain unchanged. Existing local revisions are preserved, and
source matched-family definitions retain their original version pins. Synthetic
labels remain visible; exact **Data provenance** now appears at the bottom of
each rendered case. Case lab defaults to the latest revision of its first case.

The documented Docker unittest command passed **50 tests in 5.409 seconds**,
including three new regressions for wording-only changes, preserved prior
records and corrections, restart idempotency, and existing local revisions.
Browser smoke in a disposable database verified the new narrative/facts,
bottom provenance layout, and Case lab's default version 1.1 selection.

A verified backup was created before updating the normal service. After the
restart, all **10 saved responses, 25 presentations, 10 original case versions,
and five family definitions** matched their prior JSON payloads byte-for-byte.
All ten latest cases served version 1.1 without “fictional” in their narratives
or facts. The SQLite integrity check passed. No response was submitted during
this follow-up.

Changed `twin_lab/catalog.py`, `static/snapshot.js`, `static/styles.css`, and
`static/lab.js`; updated test helpers and catalog/collection/HTTP/migration
tests, README, schema, backlog, and this report. No new dependency, commit,
push, or deployment was added.

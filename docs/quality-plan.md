# Twin Lab quality implementation plan

Prepared September 12, 2026. Status: **implemented; final evidence in
[verification](verification.md)**. The original Downloads attachment is unchanged.
Repository: `Twin-Atul-Sept-2026`. Working branch: `feat/twin-lab-v0-1`.

Implementation preserves the acceptance requirements below. The authorized
source checkpoint is `55ef561`; quality changes remain local. The single gate
is `sh tests/quality/run.sh --fast|--full`. The four approved development tools
are pinned under `tests/quality/`; they add no application dependency. Only
`persistence.py` and `migrations.py` were added as shared runtime modules.
The actual application process, response storage and operating records were
not upgraded or edited. The optional performance measurement remains deferred.

## Outcome and scope

Make changes easier to verify, preserve existing observations through upgrades,
and reduce confusing configuration. Retain the standard-library Python/SQLite
application and static browser modules. Deliver five separately reviewable phases;
each phase has tests and an independent review before the next phase begins.

This plan covers the five engineering recommendations and seven quality rules
from the discussion. It also records the lower-priority lifecycle performance
suggestion. Implementation does not approve clinical cases, complete operating
attestations, or change any actual participant or response record.

Keep the application single-user, local and synthetic-only. No AI runtime,
training, patient data, cloud services, shared deployment, EHR integration, push,
or framework rewrite is included. Development and test code runs in containers.
Private names, contacts, acknowledgments and acceptance records stay in private
runtime storage; they must not be copied into this plan or test fixtures.

## Verified starting point

- Existing code already provides domain modules, strict input validation,
  transactional saves, immutable snapshots/revisions, retry protection, lifecycle
  restrictions, and offline backup/restore/disposal operations.
- The latest completed review ran **116 tests successfully in 7.944 seconds**
  and **40 Git-exclusion checks**. These are the previous review's results,
  not a new test run for this documentation change.
- Existing tests already cover many migrations, stale writes, withdrawal,
  restoration and failure paths. Extend those tests rather than duplicate them.
- Browser workflows have manual verification records, but no committed,
  repeatable JavaScript/browser regression suite.
- Most source files remain untracked. The existing feature branch and all
  uncommitted work must be preserved.
- Collection has legacy editable permission/retention fields in addition to
  authoritative Governance settings. Generic persistence helpers are duplicated
  or borrowed across domain modules. Pilot start/session fields are incomplete.

Source contracts: [first build](../MDcopilot_Twin_First_Build.md),
[milestone 2](milestone-2.md), [milestone 3](milestone-3.md),
[schema](schema.md), [verification](verification.md), and [AGENTS.md](../AGENTS.md).
This plan supplements those contracts; current versions and behavior are recorded
in schema/milestone documentation and actual test evidence in verification.

## Decisions and implementation order

1. Preserve the existing runtime stack. Add tools only to a separate test setup.
2. Establish tests before cleanup or behavior changes. Keep formatting-only,
   persistence-only and policy/schema changes in separate review batches.
3. Use one authoritative Governance revision for new collection plans. Preserve
   old plan records and their established compatibility behavior.
4. Keep the current UTC date-boundary semantics in this milestone. Adding local
   timezone-dependent policy semantics is deferred; do not reinterpret existing
   response deadlines. Clearly label UTC boundaries in new pilot controls.
5. Add at most two shared runtime modules: focused persistence helpers and
   explicit database setup/migrations. Do not introduce a generic repository
   framework or duplicate all data contracts in another schema system.
6. Apply all seven quality rules within each phase. Phase 5 extends cross-feature
   coverage; it is not permission to postpone tests from earlier phases.

```text
Phase 1: baseline + isolated local quality gate
    -> Phase 2: browser regressions + reliable refresh
    -> Phase 3: shared persistence + explicit migration setup
    -> Phase 4: linked policy + structured pilot/session setup
    -> Phase 5: sequence/interruption coverage + final verification

Each phase: acceptance examples -> tests -> implementation -> review -> evidence
```

## Phase 1 — Source baseline and local quality gate

**Deliverables**

- Inspect branch, file inventory and existing changes. Review the exact
  source-only file list before a local baseline commit. Do not stage private
  data, generated artifacts, credentials or unrelated work. Commit only with
  explicit authorization; nothing is pushed.
- Provide one future entry point, `sh tests/quality/run.sh`, with `--fast` and
  `--full` modes. The wrapper may invoke Docker and Git metadata checks on the
  host; Python, Node, linting and test execution occur inside containers.
- Fast mode: syntax, configured static/type/format checks, existing Python tests,
  Git-exclusion checks, and whitespace checks that include new source files.
  Full mode adds browser, sequence, migration and interruption suites.
- Define suite membership explicitly. Keep existing top-level `test_*.py` tests
  in fast mode; place new full-only sequence/interruption tests in dedicated
  directories with explicit runner commands. Existing migration checks remain
  fast; expanded compatibility scenarios can be full-only. Verify test discovery
  lists so fast mode does not accidentally include or silently omit suites.
- Missing required tools, a failed check or an unrun required suite returns a
  nonzero exit status. Never install tools automatically or report a skipped
  required check as a pass. The early gate must explicitly report browser and
  fault suites as pending until their phases are complete.
- Keep a compact local result artifact with source hashes, tool versions,
  commands, counts, timings, failure identifiers and reproducible test seeds.
  Screenshots, downloads, logs and traces stay outside Git in a dedicated test
  output directory, separate from actual Twin Lab data.

**Test-only tooling, explicitly approved for implementation**

- Python: Ruff for lint/format checks; mypy for gradual type checking, starting
  with schema, persistence and lifecycle boundaries. Use existing schema modules
  for type aliases/TypedDicts; avoid parallel runtime validation definitions.
  Expand checked scope whenever a module changes, with an explicit scope list.
  No blanket suppression to manufacture a passing result.
- Browser: Playwright Test with Chromium, one worker initially, plus TypeScript
  `checkJs`/`noEmit` and unused-local checks over an explicit growing subset of
  JavaScript modules. Keep JavaScript source files; no TypeScript application
  migration or browser build step is required. Resolve existing absolute local
  imports in test configuration and use JSDoc at important boundaries.
- Parse all JavaScript using the test runner's Node runtime, distinguishing ES
  modules from the existing classic theme script. Browser smoke tests must also
  load the real import graph; syntax checking alone cannot establish that it runs.
- Pin exact package versions, lock transitive dependencies, and pin test images
  by digest after verifying compatibility with this machine. Keep Playwright's
  package and browser image versions aligned. Build tools separately from the
  application image; downloads happen during the explicitly approved setup,
  and test execution must work without external network access afterward.

Ruff supplies Python linting/formatting; mypy supports incremental adoption;
TypeScript can check JavaScript without converting it. Playwright's Docker image
contains browsers/system dependencies but still needs its matching test package.
See [Ruff](https://docs.astral.sh/ruff/),
[mypy adoption](https://mypy.readthedocs.io/en/stable/existing_code.html),
[checkJs](https://www.typescriptlang.org/tsconfig/checkJs.html), and
[Playwright Docker](https://playwright.dev/docs/docker).
Verified exact versions, transitive locks and image digests are recorded under
`tests/quality/`; see the execution record for the versions actually tested.

**Test isolation**

Use a standalone Compose file under `tests/quality/`, not an override of the
normal [Compose file](../compose.yaml), which mounts actual runtime storage.
Mount source read-only; use fresh tmpfs/temporary volumes and synthetic fixtures.
Do not mount actual `/data`, home directories, browser profiles, or the Docker
socket. The test server and browser runner share a network namespace so the
browser uses loopback and existing Host/Origin checks remain unchanged. Publish
no test ports; give the test server `network_mode: none` and let its browser
runner share that namespace. This retains loopback without external egress.
Browser tests must also fail unexpected non-loopback request attempts; a blocked
connection alone is not a passing no-external-request assertion. Set adequate
shared memory without privileged operation.
Inspect the resolved Compose configuration to prove these properties.

**Acceptance**

- A deliberate syntax error, unused import, type mismatch in checked scope,
  failing test, or excluded-data sentinel makes the gate fail with an explanation.
- Two clean runs use fresh disposable data and leave the actual application
  process, database, journals and browser tabs untouched.
- Existing acceptance tests pass. A source-only checkpoint is recorded if
  authorized; otherwise the report explicitly lists that checkpoint as pending.
- Tool setup/configuration and any formatting normalization are separate batches.

**Likely files:** `tests/quality/` runner/Compose/tool configuration and locks,
existing Git-exclusion check, `.gitignore`, `README.md`, and `AGENTS.md`.

## Phase 2 — Browser regression coverage and predictable capture

**Deliverables**

Add browser scenarios under `tests/browser/` against the isolated real API and
SQLite store. Use fabricated test-only governance and permissions. Intercept
requests only to deliberately delay, drop or reorder a specific response; normal
paths use the real server. Use observable conditions rather than fixed sleeps.

Cover the following user-visible behaviors:

- Every tab and synthetic/prototype notice; complete import graph; no unexpected
  browser errors or external requests; keyboard navigation and focus.
- Required-field errors and explicit QA acknowledgment, reset per presentation.
- Save, refresh, correction, review and JSON download with exact fabricated
  values, original snapshot/version, code and correction links preserved.
- A committed save whose reply is lost, followed by an unchanged retry: exactly
  one observation. Distinguish this from failure before server commit.
- Editable validation errors versus protected pending saves/conflicts, with
  recoverable messages and no draft silently discarded on tab changes.
- Permission initially unselected; Agree/Decline, stale permission, case review
  changes and current assignment/code checks; no human gate opened by test setup
  outside the isolated environment.
- Dark-mode keyboard toggle and reload persistence; only theme preference in
  browser local storage.

Write failing regressions before fixing capture refresh. Preserve receipt and
assignment selections when still valid; clear and explain invalid selections.
Use a request-generation token to prevent a late older refresh from replacing
newer state, including an older failure arriving after a newer success. Retain
existing protected-draft/correction behavior and server-side revalidation.

**Acceptance**

- Tests exercise real JavaScript and storage, not only element existence.
- Deterministically reversed refresh replies leave the newest state displayed.
- Valid selections survive navigation; revoked/changed selections cannot be used.
- Repeated clean runs pass with automatic retries disabled. Do not hide flaky
  failures through reruns or broad console-error exemptions.
- Existing Python restart tests remain; a dropped browser reply does not replace
  actual process/storage restart verification.

**Likely files:** `tests/browser/`, `tests/quality/`,
`twin_lab/static/capture-mode.js`, `app.js`, and verification documentation.

## Phase 3 — Consolidate persistence without changing behavior

**Deliverables**

- First extend synthetic compatibility fixtures for empty databases and supported
  versions 1, 2 and 3. Include responses/corrections, reviews, plans, assignments,
  permissions, lifecycle restrictions, retries and restored databases.
- Move shared record lookup/retry/connection behavior to a small persistence
  module. Domain modules retain validation and meaningful error messages.
  Use constant internal table names and parameterized data values.
- Move schema setup into an explicit ordered migration coordinator. Preserve
  existing version 3 behavior and seed/version identities in this cleanup batch;
  bump database/contracts only for later semantic changes.
- Keep transaction ownership explicit. Avoid `executescript()` inside a claimed
  atomic transaction, and advance the schema version only after successful setup.
  Filesystem journals have their own durability boundary; SQLite rollback does
  not roll them back. Preserve the current fail-closed recovery behavior.
- Remove replaced helper variants and constructor DDL after their callers move.
  Keep fixture seeding separate from schema changes and idempotent on restart.

**Acceptance**

- Compare original `payload` and `request_body` bytes, identifiers, timestamps,
  snapshot hashes, correction links and retention anchors before/after migration
  and repeated startup. Do not merely compare reserialized JSON.
- Unknown database versions are rejected before writes. Injected setup failure
  leaves a recoverable state and does not falsely advance the version.
- Existing retries, concurrent saves and immutable-history protections pass.
- Backend/browser behavior remains unchanged; no runtime dependency is added.
- Review shared-helper extraction separately from migration-coordinator changes.

**Likely files:** `twin_lab/persistence.py`, `migrations.py`, existing domain/schema
modules using the replaced helpers, `tests/test_migration.py`, and existing
store/catalog/collection/governance tests. Split changes by domain to keep review
batches focused; do not combine this phase with policy changes.

## Phase 4 — One policy source and structured pilot/session setup

**Deliverables: explicit new contracts**

- Add versioned governance fields for professional role, pilot start date and
  participant-facing session description/assigned-case-set limit. Old records remain exactly
  as stored; absent new fields display as unknown. Do not parse historical notes
  to infer structured facts, automatically approve records, or create permission.
- Keep date boundaries explicit in UTC: start inclusive at 00:00 on the start
  date; end exclusive at 00:00 after the close date. Existing retention remains
  anchored to the established end-of-UTC-close-date rule. Do not alter previously
  frozen deadlines or introduce a timezone conversion in a cleanup.
- Validate start <= close, session limits, empty/incomplete drafts, and values
  exactly before/at/after boundaries. New-contract human capture requires the
  explicit start/session information. Older approved records keep their existing
  gate until a deliberate new revision is saved.
- Preserve the approved calendar-year policy. If a new edit changes the close
  date, invalidate the prior administrative day conversion and show the required
  recalculation. Never silently carry a 365-day value into a leap-year interval.
  Calendar conversions receive leap-year/anniversary examples and recorded basis;
  missing or ambiguous conversions remain incomplete.
- Introduce a strict, explicitly versioned v2 collection-plan request containing
  an existing `governance_id`, codes, ownership and assignment-planning fields.
  Show notice, session limits and retention from the pinned Governance revision
  as read-only. Preserve v1 plan values/history; new edits use v2.
- Preserve strict v1 read/write/retry compatibility for existing clients during
  this milestone. An existing current v1 plan retains its established capture
  checks until an operator explicitly creates a new current plan. No migration
  auto-links a v1 plan or cuts over an active workflow.
- Prevent downgrade after that cutover: new v1 writes are accepted only while
  the current plan is v1, or for an untouched legacy initial-plan path. Once v2
  is current, reject new v1 revisions with a recoverable conflict. Identical
  historical v1 retries may return the original record without making it current.
  Test a v1 request that names a current v2 parent and tries to remove its pin.
- A v2 plan may reference draft governance for planning, but human capture requires
  that its pin equal current approved governance. Recheck at permission recording,
  presentation and submission/retry. A newer governance revision makes old links
  visibly stale; never silently rebind a plan, receipt, correction or response.
- Participant-facing session scope changes require a new governance/notice
  revision and permission under it. Assignments within unchanged approved scope
  keep their exact version and documented order. Name the limit explicitly
  `max_distinct_case_versions`: count the union of versions assigned to a physician
  across all plans pinned to the same governance revision. A plan revision must
  not reset that count. That governance revision is the durable scope boundary;
  creating a new scope requires an explicit new notice and permission.
- The assigned-case-set limit governs distinct case versions. Repeated attempts
  at one version and linked corrections consume no additional distinct-version
  allowance; they remain separate preserved observations under existing rules.
  The interface/notice must describe this accurately and must not promise a cap
  on total responses or session duration. A timed session or total-attempt cap
  would need a separately specified session model and is deferred.
- Introduce explicit contract/database versions where needed; retain old response
  schema versions and private-data exclusions in exports. Historical corrections
  keep original references and continue to obey current authorization restrictions.

**Acceptance**

- New plans have one policy editing location; historic policy fields remain
  inspectable without becoming current controls.
- Mixed v1/v2 histories, repeated migration, exact retries, unknown fields,
  stale pins and mismatched code/case/receipt combinations are tested.
- A valid current combination succeeds. Invalid or stale combinations fail with
  a recoverable explanation. Case approvals, consent, accepted roles and completed
  checks are never inferred by a migration.
- Old payloads, permissions, response links and frozen deadlines are byte-preserved.
  New session/role/contact text cannot leak into general response exports.
- Browser tests cover create/edit/read-only policy display, invalid dates,
  session limits and the deliberate transition from a v1 to a v2 plan.
- Tests prove that an additional plan under the same governance cannot exceed
  the distinct-version allowance, repeats/corrections do not consume a new slot,
  a rejected assignment adds nothing, and a new scope requires new permission.

**Likely files:** existing governance/collection schemas and domain modules,
their forms/capture module, migration setup, focused tests, and
`docs/schema.md`, `docs/milestone-3.md`, `docs/decisions.md`. Deliver pilot-contract
changes and plan-linking changes as separate batches.

## Phase 5 — Sequence testing, interruptions and final acceptance

Extend existing tests; do not replace already verified cases with weaker ones.
Use standard-library fixed seeds, a controlled clock and a small independent
expected-state model. Expected results must not call the production helper being
tested. Store the seed and action trace for reproducibility; convert every
discovered bug into a short focused regression test.

**Action sequences and invariants**

- Approve test governance -> plan/assign -> agree -> present -> submit -> retry
  -> correct -> restart -> review/export: one observation per presentation,
  no forked corrections, unchanged originals and exact presented information.
- Present -> change permission/governance/review or cross a date boundary ->
  save: stale actions rejected; no restricted or unauthorized response exposed.
- Submit -> backup -> hold/withdraw/verify -> release -> expire -> reviewed test
  disposal -> restore: original expiry/withdrawal anchors preserved, whole-chain
  restrictions enforced, no reappearance through ordinary review/export, and
  fresh governance/permission required for human capture after restoration.
- Partial restore -> verify -> later restore: original verification timing still
  applies to previously absent chains; unknown legacy policy remains unknown.

**Process interruptions**

Run a child process inside the test container. Synchronize using pipes/events at
named boundaries, then terminate only that child. Use test wrappers/patches;
do not add production fault-injection endpoints or timing-based sleeps.

- Response insert before commit; commit before HTTP acknowledgment.
- Restriction/deletion journal flush before the corresponding database commit.
- Backup rename/durable flush before manifest commit.
- Authorized test disposal before purge and during managed-copy cleanup.
- Sanitized restore immediately before and after publishing the destination.

Also simulate specific I/O errors through narrow test patches. Do not fill the
host disk, delete actual copies, kill the running application or manipulate real
governance. Filesystem restrictions may remain after an interrupted DB operation;
the correct result is preserved restriction plus explicit recovery, not a promise
that every operation rolls back to an unrestricted state.

**Acceptance**

- An acknowledged save survives restart. An unacknowledged save is either absent
  or committed once, and an identical retry resolves it without duplication.
- Journaled restrictions remain effective; malformed or missing journals fail
  closed. Backup retries recover the same snapshot and retention anchors.
- Restore exposes only a sanitized destination and never replaces the live DB.
- Every interruption has an asserted post-restart state and recovery procedure.
  Process-kill tests do not establish power-loss or hardware-failure guarantees.
- Final full gate passes from fresh disposable storage. All proposed required
  suites run; failures, skips and exclusions are reported explicitly.

**Likely files:** domain-focused sequence/interruption tests and helpers under
`tests/`, existing lifecycle/backup/restore tests, the quality runner, and
verification/recovery documentation. Correct production code only for reproduced
defects, each in its own tested change.

## Seven quality rules applied to every phase

1. **Regression first:** reproduce a bug in a test before fixing it; record the
   failing/passing evidence. Use appropriate syntax/config checks for trivial
   mistakes rather than creating tests that merely restate implementation.
2. **Static checks:** syntax-check all executable source; enforce configured
   lint/format/type scope and expand it with touched modules. Exceptions need
   a narrow reason and tracked follow-up, never silent exclusions.
3. **Sequence invariants:** assert immutable originals, explicit permission,
   single-save retries, stable retention and effective restrictions after each
   relevant action in a deterministic scenario.
4. **Failure recovery:** test meaningful interruption/I/O boundaries in disposable
   storage and document what remains committed, restricted or recoverable.
5. **Compatibility:** every contract/database change extends version fixtures and
   checks exact historical bytes, exports, IDs, hashes, links and repeated startup.
6. **Independent review:** a reviewer other than the implementer checks the
   acceptance examples, test oracle, negative paths and final diff. This is an
   engineering review, not independent clinical or operational attestation.
7. **Definition of done:** acceptance cases pass; required checks actually ran;
   failure/recovery and compatibility paths pass; documentation matches behavior;
   private artifacts remain excluded; review findings are resolved or explicitly
   deferred; and the final report records actual evidence and remaining limits.

These rules are incorporated in the existing `AGENTS.md` and verification
documentation. Do not create overlapping instruction/checklist files.
No arbitrary coverage percentage or test-count target substitutes for behavior.

## Coverage map and traceability

```text
Existing acceptance contracts
  |-- Python domain + HTTP tests ................ preserve/extend in every phase
  |-- Historical bytes + schema compatibility .... P1 baseline, P3/P4 migrations
  |-- Real browser + local API + SQLite .......... P2, expanded for P4
  |-- Temporal/action invariants ................. P5 + focused cases per change
  |-- Child-process interruption -> recovery ..... P5 + relevant earlier changes
  `-- Independent acceptance/diff review ......... every phase

Local quality runner
  fast -> syntax/static/type/format + Python + data exclusion
  full -> fast + browser + compatibility + sequences + interruptions
```

- R1 source checkpoint/local gate -> Phase 1.
- R2 browser regression automation -> Phase 2.
- R3 single policy editing location -> Phase 4.
- R4 shared persistence/migrations -> Phase 3.
- R5 structured pilot/session and refresh behavior -> Phases 2 and 4.
- Q1 regression tests -> every phase; Q2 static checks -> Phase 1 onward;
  Q3 sequences -> Phase 5 plus per-change examples; Q4 interruptions -> Phase 5;
  Q5 compatibility -> Phases 3/4 and all schema changes;
  Q6 independent review and Q7 completion checklist -> every phase.

## Performance follow-up and rollback

The review observed repeated lifecycle/database reads on small fabricated data.
After Phase 5, optionally measure review/export at increasing synthetic sizes.
Optimize only if measured response time or operation counts justify the work.
Use request-scoped batching with the same restrictions and journal validation;
avoid persistent caches that could serve data after withdrawal. Compare results
and query/file-read counts before/after. This work is outside the five-phase
critical path and must not delay correctness improvements.

Before an authorized live upgrade, make and verify a controlled backup and retain
the authoritative journals. Rehearse the upgrade/restore in a separate directory.
Source rollback may be used for behavior-preserving changes. After a schema change,
do not run an older incompatible binary against the newer database; use a forward
fix or a separately restored, journal-reconciled copy with the documented barrier.
Never replace live data or erase newer observations automatically.

## Plan review and execution record

Architecture, code quality, test coverage and performance were evaluated using
the engineering-plan checklist and separate backend/frontend reviewers. Their
findings are incorporated: test Compose isolation, loopback browser routing,
versioned plan compatibility, SQLite/filesystem transaction boundaries,
independent expected results and deterministic interruption barriers.

The user explicitly approved both the local source checkpoint and the four
test-only tools. Phase 1 established isolation/static checks and separately
reviewed formatting. Phase 2 added browser regressions before the refresh fix.
Phase 3 separately reviewed helper extraction and transactional setup. Phase 4
delivered structured pilot contracts before linked plans. Phase 5 adds independent
seeded models and deterministic process/I/O recovery checks. Each changed
behavior has focused tests and a separate engineering reviewer.

The final commands, counts, timings, negative baselines, source/artifact evidence
and limitations belong in [verification](verification.md). Human pilot operations
remain subject to their own requirements; automated engineering tests do not
supply clinical approval, device attestations or participant permission.

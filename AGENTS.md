# Twin Lab local development

Read `MDcopilot_Twin_First_Build.md`, `docs/milestone-2.md`, and `docs/milestone-3.md`. Preserve the original
brief and README discussion link. The user authorized the local review, matched
families, and collection-planning extension after the first milestone.

## Boundaries

- Standalone, single-user, local synthetic-case decision capture only.
- Source fixtures remain synthetic, unreviewed, ineligible demo placeholders.
  Local reviewer decisions attach to exact immutable case versions. Approval
  alone never grants study eligibility; this build remains demo-only.
- Never add AI advice, answer keys, diagnosis probabilities, training, analytics,
  patient records, cloud services, EHR connections, or public deployment.
- Do not import the separate MDcopilot application's runtime or credentials.
- Use the Python standard library, SQLite, and local HTML/CSS/JavaScript at runtime.
  The user approved Ruff, mypy, Playwright Test and TypeScript for the isolated
  test environment on September 12, 2026. Ask before adding other dependencies.
  Pin packages and container images; downloads occur during explicit setup only.
- Run application code and tests in Docker. Bind the published port to loopback.

## Data and implementation

- Keep synthetic fixtures in `fixtures/`; runtime responses, exports, logs,
  databases, and credentials must stay out of Git. Default storage is outside
  this repository at `~/.local/share/twin-lab`.
- Validate cases and requests at the boundary; reject unknown schema fields.
- Retain original submitted values separately from normalization, the immutable
  presentation snapshot, UTC timestamps, and version/provenance metadata.
- Commit saves before acknowledging success. Retried saves are idempotent;
  corrections append linked records. Never edit or delete observations through
  capture/review. The user-authorized lifecycle extension permits disposal only
  through the separate offline preview-and-confirm process, covering full chains
  and managed copies with a durable deletion ledger. Never execute disposal of
  actual local records without an explicitly approved plan. Legacy records gain
  no inferred permission, fabricated status, retention period, or owner.
- This is application-level append-only behavior, not tamper-proof storage.
- Keep modules focused, use parameterized SQL, and display response text as text,
  never HTML. Surface errors without logging response content.

## Verification and handoff

- Use `sh tests/quality/run.sh --fast` for focused work and `--full` before handoff.
  Run tests with the standalone test Compose configuration, never the application
  configuration that mounts actual data. Missing or unrun required checks fail.
- Keep all test databases, browser downloads, traces and reports in disposable
  storage or the dedicated quality output directory outside the checkout.
  Never mount actual response storage, home directories, browser profiles or the
  Docker socket into a test container. Test execution has no external network.
- Exercise case display, validation, save/retry, restart, correction, local review,
  and JSON export. Test that runtime data and credentials are Git-ignored.
- Report actual test results and any unrun checks. All screens must retain the
  synthetic prototype / unreviewed / not validated clinical tool notice.
- Work on the user-requested local feature branch. Do not commit, push, publish,
  deploy, or change repository visibility unless explicitly requested.

Apply these seven quality rules to each reviewable change:

1. Reproduce defects before fixing them; record failing and passing evidence.
2. Run syntax, lint, format and the documented type-check scope. Extend that
   scope for changed modules; explain narrow exceptions rather than hiding errors.
3. Check action sequences for immutable originals, explicit permission,
   idempotent saves, fixed retention anchors and effective restrictions.
4. Exercise meaningful failure/recovery boundaries using fabricated temporary
   data. Never kill the actual application or dispose of actual records in tests.
5. Compare exact historical payload/request bytes, identifiers, timestamps,
   hashes and links across contract changes and repeated startup.
6. Obtain engineering review from a reviewer other than the implementer.
   Automated review is not a clinical review or an operational attestation.
7. Finish with passing acceptance checks, actual test evidence, updated docs,
   ignored private artifacts, resolved review findings and explicit limitations.

Keep formatting, persistence cleanup and policy changes separately reviewable.
Do not use test counts or an arbitrary coverage target as substitutes for behavior.
The approved source checkpoint is local only; authorization does not permit push
or deployment. A schema upgrade must first be rehearsed in disposable storage;
never run an incompatible older binary against a newer database.

Local case review, matched families, and draft collection rules are in scope.
Versioned governance, participant permission, gated local human demo capture,
and tested lifecycle tools are also authorized. The project user explicitly
approved the incorporated demo governance documents and policy choices at
2026-09-10T23:33:19Z; canonical documents record revision 0.2 and approval source
`explicit_user_instruction`. Treat their demo policy values as approved project
choices, without inferring a personal identity, accepted role, qualified privacy
review, completed operational record or participant agreement. The original
Downloads documents remain unchanged. Future research wording stays a deferred
draft. Preserve unset contacts/pilot dates and unaccepted role appointments.
One-year administrative periods mean a calendar year; do not invent a 365-day
equivalent before the pilot close date and calendar handling are recorded.
Human capture requires explicit complete local approvals and recorded checks;
do not check boxes or sign on anyone's behalf. Keep private governance, permission
receipts, exports, and deletion ledgers outside Git and general response exports.
Actual study collection, model comparisons, and MDcopilot integration remain
deferred. Never invent clinical approval, participant consent, additional policy
choices or owners. Document approval never changes legacy response provenance or
retention, and does not authorize disposal of existing records.

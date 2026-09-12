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
- Use the Python standard library, SQLite, and local HTML/CSS/JavaScript. Ask
  before adding third-party dependencies. Pin the container runtime by digest.
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

- Run `docker compose run --rm twin-lab python -m unittest discover -s tests -v`.
- Exercise case display, validation, save/retry, restart, correction, local review,
  and JSON export. Test that runtime data and credentials are Git-ignored.
- Report actual test results and any unrun checks. All screens must retain the
  synthetic prototype / unreviewed / not validated clinical tool notice.
- Work on the user-requested local feature branch. Do not commit, push, publish,
  deploy, or change repository visibility unless explicitly requested.

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

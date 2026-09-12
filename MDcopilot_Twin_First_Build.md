# MDcopilot Twin — First Build Brief

**Repository:** `atulk-mdcopilot/Twin-Atul-Sept-2026`  
**Milestone:** Twin Lab v0.1 — synthetic-case decision capture  
**Status:** Proposed implementation instructions; not application code and not pushed to GitHub.  
**Prepared:** September 8, 2026 (America/New_York).

## Verified starting point

At inspection, the repository's `main` branch contained only `README.md`, consisting of the repository title and a shared ChatGPT discussion link. No application, dependencies, database schema, tests, or original case workbook were present in that branch. The connected GitHub session reported read access but no push access, and repository visibility was public. Re-inspect before making changes because this state can change.

This brief is self-contained. Do not assume the coding session has access to earlier chats or the separate MDcopilot application. Preserve the existing README's discussion link as background, but do not mistake that link for an implemented specification or imported source code.

## Objective

Implement the smallest runnable, local Twin Lab workbench for presenting synthetic adult GI-bleeding cases after initial stabilization and capturing a physician's decisions before any AI advice is displayed.

This milestone builds the observation pipeline. It does not learn a twin, measure clinical accuracy, give treatment recommendations, or authorize clinical deployment. Expand later to abnormal liver tests and diarrhea only after the first workflow is reviewed.

The first successful demonstration is:

> Open a synthetic case → enter a next action and information request → save → restart the application → retrieve and export the same versioned response.

## Working instructions for the coding agent

Inspect the working directory, repository remote, current branch, existing instructions, uncommitted changes, and installed tooling first. Report what you find. Preserve unrelated work. If a stack has since been added, reuse it. Otherwise select a minimal, locally runnable stack, document the decision, verify dependency installation instructions against official documentation, and pin dependencies. Avoid a separate service or cloud dependency unless it is actually needed.

Implement on a local feature branch such as `feat/twin-lab-v0-1`. Do not deploy, push, publish, alter repository visibility, or connect patient systems as part of this task. Do not copy the separate MDcopilot production codebase or invent its APIs. Record future integration points as proposed interfaces.

## Required workflow

### 1. Select a synthetic case

Create five small, explicitly synthetic UI/demo fixtures. These are newly authored placeholders, not recovered cases from the original 100-case workbook. Mark them `review_status: unreviewed` and `eligible_for_study: false` until reviewed by the clinical lead. The number five is a software-testing convenience, not a research sample-size target.

Each case needs a stable identifier, case-family identifier, version, provenance, care setting, visible narrative, and structured decision-time facts. Do not use real patient information. Do not imply that a synthetic diagnosis or suggested action is established ground truth.

Clinical reviewers will later decide whether the cases are suitable for elicitation. The software must not claim to validate clinical plausibility by itself.

### 2. Capture an unaided response

Provide a simple response form with:

- A physician code, without requiring a name or email.
- The physician's next action, as text or a structured selection with an "other" option.
- Information the physician would request next.
- What would change the physician's decision.
- Optional brief rationale and optional self-reported confidence in that decision.

Do not require hidden-chain-of-thought-style narratives. Do not display model advice, a suggested diagnosis, an answer key, or a supposed physician preference before submission. Allow the physician to record insufficient information rather than forcing certainty.

Label confidence as self-reported decision confidence, not disease probability. Do not invent numerical diagnostic probabilities in this milestone.

### 3. Persist, review, and export

Store responses durably on the local machine using a documented, simple persistence mechanism. A successful save must survive an application restart. Provide a clear error if a save fails; never display a success state before persistence succeeds.

Each response must retain:

- Response ID, physician code, case ID, case family, case version, and response-schema version.
- The exact visible case snapshot or a content hash with an immutable referenced snapshot.
- Presentation and submission timestamps.
- Original submitted values and any normalized fields kept separately.
- Whether AI advice was shown (`false` in this milestone).
- Collection purpose (`demo` for the starter fixtures) and case-review status.
- An optional reference to an earlier response when an explicit correction supersedes it.

Do not silently overwrite earlier submissions. Prevent duplicate records from an accidental double click or retried save. Deliberate corrections should append a linked revision. Application-level append-only behavior is not a claim of tamper-proof storage; document that limitation.

Provide a local response-review screen and versioned JSON export. Keep physician responses, local databases, exports, logs containing response text, and credentials out of Git. Place synthetic fixtures separately from runtime data so the former may be committed without the latter.

## Repository deliverables

Create or update these documents while preserving any existing instructions:

- `AGENTS.md`: Scope, synthetic-only boundary, testing expectations, data-handling rules, and deferred features.
- `docs/scope.md`: This milestone's inclusion/exclusion criteria and future MDcopilot integration boundary.
- `docs/decisions.md`: Architecture decisions, assumptions, and unresolved questions.
- `docs/backlog.md`: Ordered next tasks, including clinical case review, matched case families, configuration, and later model comparisons.
- `README.md`: Exact setup, start, test, storage-location, export, and local-data cleanup instructions.

Also deliver the runnable application, typed or otherwise validated case/response schemas, five demo fixtures, relevant automated tests, dependency lockfiles, and an appropriate `.gitignore`.

## Required acceptance tests

1. A valid synthetic fixture displays without exposing any hidden labels or future outcome fields.
2. Empty or malformed required fields cannot be saved as valid responses.
3. A response retains its case version and original submitted values.
4. Saving, restarting, and reading back returns the same response.
5. An accidental duplicate submission creates no extra observation.
6. An explicit correction preserves the original and links the new revision.
7. Exported JSON matches the documented schema and the saved content.
8. Local response data and credentials are not staged by a normal `git add`.
9. No LLM API request, patient-system integration, analytics transmission, or automatic model update occurs.
10. All screens clearly identify the application as a synthetic-case prototype, not a validated clinical tool.

Run the tests and a basic end-to-end smoke test. Report actual commands and results. Distinguish passed, failed, and unrun tests; do not claim completion merely because code was generated.

## Explicitly deferred

Do not add fine-tuning, prediction of physician choices, diagnostic probability estimation, guideline retrieval, multi-agent orchestration, automated case selection, live patient records, EHR integration, cloud synchronization, public hosting, authentication infrastructure for a deployed service, billing, or clinical orders.

No authentication infrastructure is required for a single-user local demo; this is not permission to expose it on a public or shared network. Bind locally and document its limitations.

The public repository may contain synthetic source fixtures and source code only as authorized. Actual physician-response datasets remain outside it. Changing repository visibility does not by itself make it suitable for patient information.

## Completion report

At the end, provide:

1. What was implemented and which files changed.
2. The exact command to run the application and where local data is stored.
3. Test commands, actual results, and any remaining failures.
4. A short walkthrough of the case → response → persistence → export flow.
5. Assumptions and deferred work, including case review before study use.
6. Confirmation that no changes were pushed or deployed.

The next human review is of the case content, response form, and data provenance—not an assessment that a physician twin has already been learned.

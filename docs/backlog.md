# Ordered follow-up backlog

The [quality implementation plan](quality-plan.md) defines the proposed local
engineering work: a source checkpoint and quality gate, automated browser tests,
shared persistence, linked policy/pilot setup, and recovery testing. Follow its
phase dependencies and acceptance checks separately from the operational and
clinical decisions below. Planning does not mark any implementation complete.

The first local extension now provides immutable case reviews/revisions, five
matched demo pairs, versioned draft collection rules, manual pinned assignments,
and verified local backups. The governance extension adds exact permission,
capture gates, lifecycle restrictions and explicit disposal/restoration tools.
The original response history remains intact; new fabricated capture requires
an explicit acknowledgment. See [milestone 3](milestone-3.md).
The following are still future work; local review approval and complete draft
rules do not enable study collection.

1. **Clinical case and workflow review.** Have the clinical lead review every
   current case version, its provenance, decision-time facts, and form wording. Record
   reviewer decisions and revised versions in Case lab before considering any
   study use. Keep source fixtures unreviewed and all local captures ineligible.
   Starter wording revision 1.1 removes “fictional” while keeping explicit
   synthetic labeling and bottom-of-case provenance; this is not clinical review.
2. **Review the matched design.** Review each declared variation and the facts
   held constant, determine whether it asks a useful comparison question, and
   record revisions. A software assertion that only one fact changed does not
   establish clinical plausibility, representative sampling, causal isolation,
   or the absence of order effects. Family definitions currently pin the original
   versions; a future family-revision workflow requires separate scope.
3. **Complete operational governance.** The demo documents and policy values
   have project-user approval recorded at 2026-09-10T23:33:19Z. Record the missing
   operator/contacts, accepted people, exact notice/session, pilot close date and
   qualified review determination in Governance. Apply the approved demo periods;
   calculate the permission/audit calendar-year day counts only after the close
   date and calendar handling are reviewed. Reconcile the completed notice
   with verified device/access controls, controlled copies and administrative
   retention procedures. Keep operational drafts incomplete until their remaining
   decisions and attestations are recorded; document approval remains preserved.
   Choose codes/assignments in Collection plan and obtain explicit participant
   permission only after local human-demo approval and operational rehearsal.
4. **Study readiness decision.** Before separately authorized study collection,
   review the local permission/lifecycle controls, code identity handling, access,
   assignment ordering, administrative retention and external-copy handling.
   Specify a new purpose/eligibility contract and review its boundaries.
   This application currently has no study-collection enabling mechanism.
5. **Local operational rehearsal.** Have the backup owner create a backup and
   restore it to a separate directory, inspect its records, and confirm the
   recorded backup plan works. Assess automated local scheduling/deletion and
   multi-user needs only if the approved workflow requires them. Current backup
   frequency settings do not schedule jobs. Physical removal requires the explicit
   reviewed disposal process; administrative receipts and unmanaged copies need
   documented operator follow-through. Never discard current lifecycle journals
   while older backups could resurrect restricted records.
6. **Additional clinical domains.** Consider abnormal liver tests and diarrhea
   only after reviewing the GI-bleeding workflow; create reviewed, separately
   versioned fixtures rather than expanding scope silently.
7. **Proposed MDcopilot interface.** Draft a separate contract for a reviewed
   synthetic export/import adapter. Identify authorization and governance needs.
   No production API, patient record, or credentials are connected by this work.
8. **Later model comparisons.** After reviewed cases, an appropriate collection
   design, and explicit authorization, define offline comparison questions and
   evaluation criteria. Keep unaided physician observations separate from model
   outputs. No model advice, training, fine-tuning, probability estimates, or
   learned-twin claims belong in this milestone.

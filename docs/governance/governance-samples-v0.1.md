# MDcopilot Twin Lab — Approved Demo Governance Documents v0.2

**Status:** APPROVED for the project's demo governance documents and policy choices.
**Approval recorded at:** `2026-09-10T23:33:19Z`.
**Approval source:** `explicit_user_instruction` — “Incorporate the documents as being approved”.
**Approved by:** `project_user`; no personal identity or professional role is inferred.
**Approval scope:** `demo_governance_documents`.

This records project-user approval of the demo documents and their policy values.
The participant notice still needs its operational details completed and checked
before use. No role acceptance, qualified privacy review, institutional approval,
participant agreement, or actual control verification is created by this record.
Research wording remains a deferred draft, and actual physician capture remains
disabled until the separate local governance and permission gates are satisfied.

**Revision history:** the supplied v0.1 documents and the initial repository
adaptation were draft/unapproved. Revision 0.2 records the subsequent explicit
project-user approval; it does not rewrite that earlier history.
The two supplied Markdown files were byte-identical;
source SHA-256: `41cc4b49ba96fa101b240b45487917525711632bc2b912fdd195a9c336ad9ee6`.
This copy uses “synthetic” and distinguishes the ten-case catalog from a proposed
five-case session. Both original Downloads files remain unchanged. The
[JSON companion](twin-governance.example.json) records the same approval and
policy values; its existing filename/schema identifier are retained for continuity.
See [the implementation contract](../milestone-3.md) for supported controls and
remaining operational decisions; this document does not override that contract.
**Prepared:** September 9, 2026.
**Companion brief:** `MDcopilot_Twin_First_Build.md`.
**Scope:** A single-user, locally running prototype that displays synthetic adult GI-bleeding cases after initial stabilization and captures unaided physician responses. No patient data, model advice, model training, cloud service, clinical deployment, or public release of physician responses.

## 1. Operational prerequisites before participation

Identify the legal operator, participant contact, privacy contact, local data custodian, authorized reviewers, and planned pilot close date. Have the appropriate privacy/legal reviewer review the completed notice and document any required institutional research determination. Test the actual controls before promising them to participants. The JSON companion's demo policy values are approved project choices, but the operator/contact fields remain unset and role appointments remain unaccepted. Document approval does not enable actual physician-response collection.

Synthetic patients do not eliminate the fact that actual physician responses are information about living people. Research based on interactions with physicians can remain human-subject research even when responses are coded. Do not independently declare the activity exempt or outside research oversight merely because it uses synthetic cases. [S1, S2]

Use completely fabricated QA responses while these prerequisites remain unresolved. Those are software fixtures, not observations of a physician. Do not silently relabel real demo responses as study observations.

## 2. Approved demo permission wording — operational completion required

**Document approval:** recorded above. **Participant-ready:** no. Complete the
bracketed operator/contact/review/session fields, verify the described controls,
record the required local operational approval, and offer an initially unselected
participant choice. This document is not itself a participant permission receipt.

### MDcopilot Twin Lab: permission to participate in a synthetic-case software test

**Operator:** [Legal entity operating this prototype]
**Project contact:** [Name and working email/phone]
**Privacy/withdrawal contact:** [Name and working email/phone]
**Document version:** DEMO-PERM-v0.1
**Project review status:** [Document actual determination; do not imply IRB approval]

**Purpose and activities.** You are invited to help test whether Twin Lab reliably displays synthetic clinical cases and records, retrieves, corrects, and exports your responses. You will review an assigned set of synthetic adult gastrointestinal-bleeding cases and enter your next action, the information you would request, and what would change your decision. [Before participation: specify the session limit; five cases per session remains a planning option, while the current catalog contains ten cases in five matched families.] Brief explanations and confidence ratings are optional. A session is expected to take approximately 10–20 minutes; this is an unvalidated planning estimate, and you may stop sooner. This version does not provide clinical advice, train a physician twin, or assess your professional competence.

**Information collected.** We will record a coded participant identifier; your submitted answers; optional rationale and self-reported confidence; case and response versions; the exact case information presented; timestamps; and any linked corrections. No audio, video, screen recording, patient records, or unnecessary personal identifiers will be collected. Please do not include information about real patients, colleagues, or confidential institutional matters.

**Permitted use.** Your responses may be used only to test and improve this prototype's data-entry, storage, correction, review, and export functions. They will not be used for model training, physician-behavior research, external publication, public demonstrations, advertising, or patient-care recommendations under this permission. Those uses require separate review and permission. Project staff will not use or voluntarily disclose individual responses for employment, credentialing, promotion, discipline, or physician ranking. This restriction does not override a legally compelled disclosure.

**Privacy and risks.** Responses will be stored outside the source-code repository on a locally controlled device protected by operating-system access controls and device encryption. Access will be limited to the designated data custodian and specifically authorized reviewers who need it for this test. Any approved export will remain under the same access and retention controls. No response text will be transmitted to external AI services, analytics services, or public hosting. These controls must be verified before this wording is used. The main risks are loss of confidentiality, unintended identification, professional or reputational harm, and discomfort answering cases. A participant code reduces direct identification but does not guarantee anonymity, especially in a small pilot. Complete confidentiality cannot be guaranteed, including where disclosure is legally required.

**Retention.** Active responses and linked corrections will be deleted at the earlier of 90 days after the original submission or 30 days after this pilot closes. Local exports will be deleted within 30 days of creation or when their source records expire, whichever is sooner. Restricted backup copies, if used, may remain for up to 30 additional days after active deletion; they will not be used for new analysis and any restoration will reapply outstanding deletions. Minimal permission, access/export, and deletion records, without your response text, will be retained for one calendar year after pilot closure. These are approved project policy choices, not statutory defaults. Any known legally required exception must be explained before participation. A later documented legal hold will be limited to the affected records, with notice where legally permitted.

**Voluntary participation and withdrawal.** Participation is voluntary. You may skip cases or stop without penalty or an adverse employment or professional decision by the project. To request a copy, correction, or deletion, contact the privacy contact and provide your participant code or permission receipt. Upon receipt of a withdrawal request, we will stop further collection and use while reasonably verifying the request. Active data under the project's control will be deleted within 30 days after verification, or by the scheduled expiry if sooner, unless a documented legal requirement prevents it. Backups will expire as described above. We may retain a minimal record of permission and withdrawal, and non-identifying software defect summaries. Corrections preserve earlier submissions until the applicable retention deadline; withdrawal or expiry can remove all linked revisions. No general release, model training, or publication of your responses is authorized here.

**Benefits, payment, and rights.** There is no guaranteed direct benefit. This approved wording provides for no payment and no participation fee; revise the notice before use if compensation or costs are introduced. Participation does not waive your legal rights or authorize use of your name, likeness, or professional identity as a deployed twin. Intellectual-property ownership, compensation, licensing, and future commercial use require separate written terms. You may ask questions and keep a copy of this notice.

**Acknowledgment:**

> I have read this notice, had the opportunity to ask questions, and voluntarily agree to the limited software-testing uses described above. I understand that this does not authorize model training, publication of my responses, or deployment of a twin representing me.

Participant code: [issued code]
Choice: [Agree / Decline — neither preselected]
Date/time: [recorded timestamp with timezone]
Permission document version: DEMO-PERM-v0.1
Permission receipt ID: [generated ID]

Provide a copy of the accepted version. This demo document is not a substitute for an approved research consent process or any required signed-consent documentation. [S3]

## 3. Future research wording — DEFERRED DRAFT / NOT ACTIVE

The following insert remains a draft outside the demo-document approval scope.
It is for a later full, institutionally reviewed research consent, not a
stand-alone consent or a feature to enable now:

> This research studies whether a model can predict your decisions on unfamiliar synthetic clinical cases. With your permission, we will analyze and use your coded responses to develop and evaluate a physician-specific research model. A prediction describes estimated behavior; it is not proof of medical correctness or a reproduction of your private mental processes. Participation involves [number and type of sessions] over [duration], with [compensation/cost terms]. Risks include loss of confidentiality, incorrect characterization of your clinical judgment, and professional or reputational harm. There is no guaranteed personal benefit. Access, vendors, data locations, retention, research oversight, and rights/complaints contacts are listed in [approved protocol and privacy notice]. Your responses or trained models will not be publicly released, licensed for clinical use, used for employment decisions, or presented under your name without the separate authorizations and agreements specified in that protocol.
>
> You may stop further participation at any time. After withdrawal, we will stop collecting new responses and stop new training on your withdrawn records. We will [state the approved treatment of previously collected data and future analysis]. Records needed for required research documentation may be retained with restricted access for [specified period]. Previously published non-identifying aggregate findings cannot necessarily be withdrawn. We will not promise that deleting a record removes its influence from an existing model; the protocol must specify model suspension, retirement, or retraining when needed. No public model release is authorized by this sample.

Do not leave the bracketed withdrawal policy unresolved before use. OHRP recommends explaining whether existing data will be retained and analyzed after withdrawal; cessation of participation and erasure of existing research data are not the same thing. [S4]

Use distinct, initially unselected decisions for core research participation, optional recontact, and any proposed secondary data sharing. Named representation, commercial licensing, identifiable quotation, and clinical deployment require separate specific agreements/review and must not be bundled into today's demo permission. Do not automatically migrate old demo observations into research.

## 4. Approved demo retention schedule

The demo periods below are approved project policy choices. RET-RES and RET-MOD
remain deferred and disabled; their future-research proposals are not activated
by this approval. Regulatory background is identified separately. The operator
must still set a pilot close date and named custodian. Automatic extensions are
prohibited. Existing responses do not gain a policy, permission receipt, new
classification, or changed expiry from document approval.

| Code | Record class | Approved demo period / start event | Owner | Disposal / access rule |
|---|---|---|---|---|
| RET-FIX | Synthetic case fixtures and fabricated QA answers | Project/code lifecycle; review annually | OWN-CLIN | Authored source fixtures/test data may remain in version control after checking that no real responses, identities, or patient information are present. Captured runtime answers remain outside Git, including fabricated QA captures. |
| RET-DEMO | Actual demo physician responses, linked corrections, and associated runtime case snapshots | Earlier of original submission + 90 days or pilot closure + 30 days | OWN-DATA | Delete all linked revisions and associated runtime copies. A correction/export does not restart the original clock. Shared synthetic source fixtures may remain. |
| RET-XREF | Optional participant identity-to-code crosswalk | Avoid creating for the single-user demo. If needed, remove within 30 days after the final linked response is removed, unless a documented required record needs limited linkage | OWN-DATA | Keep separately encrypted; no Git, analysis export, or general developer access. Any legally retained identity record is separately restricted and does not make other data anonymous. |
| RET-EXP | Local JSON/CSV exports | Earlier of export creation + 30 days or the earliest expiry of any included record | OWN-DATA | Register copies and delete/regenerate the export when any included record expires or is withdrawn. All copies inherit the source purpose restrictions. |
| RET-LOG | Technical diagnostic logs | 14 days from event creation | OWN-ENG | No responses, free-text fields, patient information, secrets, or unnecessary identifiers in logs. |
| RET-BAK | Approved local encrypted backups, if any | Rolling 30 days from backup creation; no affected content more than 30 days beyond active deletion | OWN-DATA | No uncontrolled cloud backup. Reapply deletion ledger before a restoration is used. Do not rejuvenate expired data by copying an old backup into a new one. |
| RET-PERM | Minimal permission/version/withdrawal records | 1 calendar year after pilot closure | OWN-PRIV | Approved administrative policy for the demo, not a legal minimum. Keep only what is needed to document the permission and its disposition; no response narrative. |
| RET-AUD | Minimal access/export/deletion receipts | 1 calendar year after pilot closure | OWN-DATA | Event, actor, record/receipt ID, policy version, reason, and time; no deleted content. Restricted, not public. |
| RET-RES | Future approved research source data and analysis artifacts | Proposed starting point: 3 years after study completion, subject to the approved protocol and any longer required period | OWN-METH | Disabled in this milestone. Do not apply the demo's 90-day rule to regulated study records by default. |
| RET-MOD | Physician-specific profiles learned from responses, embeddings, retrieval stores, or trained weights | No collection/creation in v0.1; later schedule required before enabling | OWN-METH | Model retirement, access limits, withdrawal effects, and any mandatory archive must be specified separately. |
| RET-PHI | Patient records or accidentally entered patient information | Prohibited; no routine retention class | OWN-PRIV | Stop use, restrict access, and follow incident/legal review. Do not silently keep it, redistribute it, or immediately erase evidence subject to a hold. |

The application currently records administrative periods as whole days. Keep
those operational fields unset until the pilot close date is known; then record
the reviewed day count matching the calendar-year anniversary, including the
applicable leap-year handling. Do not silently replace “one calendar year” with
365 days. Administrative record retirement, diagnostic-log handling and detached
copy cleanup require documented custodian procedures; approving their policy does
not create an automatic cleanup job.

### Regulatory distinctions

HHS describes a minimum of three years after completion for certain research records under applicable human-subject regulations, including consent documentation when required. This is not a universal raw-data retention rule. Institutional, sponsor, state, and other applicable requirements can be longer. [S2]

The HIPAA Privacy Rule does not itself prescribe a universal medical-record retention period. [S5] Required Security Rule documentation for regulated entities is retained for six years from creation or last effective date, whichever is later. That is not a six-year requirement for every demo response, export, or diagnostic log. [S6]

Do not use a blanket "seven-year HIPAA minimum." The privacy reviewer should document which rules actually apply to this operator and record class. A genuine retention obligation or legal hold takes priority over a demo deletion target, but not as a blanket reason to continue ordinary analysis or retain unrelated records. Document authority, affected records, custodian, review date, and eventual release; tell participants about material exceptions where permitted.

### Deletion versus append-only corrections

The observation workflow preserves earlier submissions against silent editing; this is not an indefinite retention mandate. A separate authorized deletion process must purge eligible content, linked corrections, exports, and expired backups. Keep only the minimal deletion receipt. Test this on fabricated data before making the consent's promises. Document the method and limitations of local storage deletion, including journals, temporary files, backups, and the device's encrypted storage; do not equate an SQL delete or a hash with guaranteed forensic erasure or anonymity.

## 5. Owner codes and proposed assignments

An owner code identifies operational accountability. It does not establish legal ownership of data, the software, physician expertise, or trained models. These assignments are proposals only; no person has been notified or has accepted a role by this document.

| Owner code | Role | Proposed person | Responsibility |
|---|---|---|---|
| OWN-PROJ | Project sponsor | Atul / project lead — proposed, acceptance required | Confirm scope and operator; name accountable personnel; authorize milestone progression after required reviews. |
| OWN-CLIN | Clinical lead | Atul / clinical lead — proposed, acceptance required | Review every assigned case version and the response form; approve scope boundaries; keep software-demo review separate from study eligibility. |
| OWN-ENG | Engineering lead | Unassigned | Implement persistence, permission versioning, corrections, export, expiry, and data isolation. |
| OWN-DATA | Data steward / local custodian | Unassigned | Issue participant codes, control data access, inventory exports/backups, process withdrawal, and verify cleanup. |
| OWN-PRIV | Privacy/governance reviewer | Unassigned; qualified reviewer required | Review permission, retention, actual applicability of law, required research determination, incident response, and proposed access. |
| OWN-QA | Test reviewer | Unassigned; distinct reviewer where feasible | Witness/save evidence of persistence, privacy, deletion, authorization and no-network-transmission tests. |
| OWN-METH | Methods/statistical lead — later stage | Unassigned; deferred | Design study, protected dataset splits, evaluation criteria, and research data/model policies. |

One person may hold more than one operational role in a small demo, but record that explicitly. Engineering or data custody does not confer clinical, privacy, or IRB approval authority. For formal research, obtain independent methodological/clinical and privacy review appropriate to the study; founder self-review alone is not a substitute.

For every appointment, record role code, actual person, role email/contact, accepted_at, effective_from, backup person if applicable, and status. Keep the staff/contact registry private. Role codes and placeholder task assignments can be placed in Git; do not publish participant mappings or private contact information.

## 6. Participant and record codes — separate namespace

| Code type | Example (illustrative only) | Rule |
|---|---|---|
| Physician participant | PHY-7Q4M9C2K | Generate randomly; do not encode initials, birth date, institution, license, or employee ID. Check uniqueness. Not an authentication credential. |
| Staff actor | STF-5R8N2V7P | Random staff ID, resolved through a private staff registry. Not the same as role code. |
| Case | GI-SYN-001 | Synthetic fixture identifier. |
| Case family | GI-FAM-001 | Shared by matched variants for future split control. |
| Permission receipt | CONS-<UUID> | References exact permission text/version/hash and selection. |
| Response | RESP-<UUID> | Links the participant, case snapshot, and permission receipt. |
| Consent document | DEMO-PERM-v0.1 | A document version, not a participant ID. |

Treat coded physician responses as confidential, not anonymous. In a one-physician prototype the identity may be obvious even without a crosswalk. Codes do not themselves grant access, verify identity, or authorize export. [S1]

Suggested response/governance metadata:

```json
{
  "physician_code": "PHY-7Q4M9C2K",
  "response_id": "RESP-<UUID>",
  "permission_receipt_id": "CONS-<UUID>",
  "permission_version": "DEMO-PERM-v0.1",
  "collection_purpose": "demo",
  "case_review_status": "unreviewed",
  "eligible_for_study": false,
  "clinical_owner_code": "OWN-CLIN",
  "data_owner_code": "OWN-DATA",
  "retention_policy_code": "RET-DEMO",
  "retention_anchor_at": "<original-submission UTC timestamp>",
  "expires_at": "<calculated UTC timestamp>",
  "training_allowed": false,
  "research_reuse_allowed": false,
  "public_release_allowed": false,
  "legal_hold_id": null
}
```

The sample strings are placeholders, not existing participants or response records. Do not give a real participant any of these example IDs automatically.

## 7. First assignments / backlog

"Accountable" is the person who signs off; "Responsible" performs the work.
The demo documents and policy values have project-user approval. Role appointments,
operational sign-off and participant permission remain separate; no GitHub
assignment or accepted person appointment is created by this document.

| Task | Deliverable | Accountable owner | Responsible owner | Required review / gate |
|---|---|---|---|---|
| GOV-001 | Operator name, contacts, planned close date, accepted role register | OWN-PROJ | OWN-PROJ | OWN-PRIV checks applicability and missing oversight decisions. |
| GOV-002 | Complete operational notice and retention approval using the approved demo documents | OWN-PRIV | OWN-PRIV | Project document/policy approval is recorded; OWN-DATA still confirms practical deletion/export/backup commitments and OWN-CLIN checks completed purpose wording. |
| GOV-003 | Review every version to be assigned from the ten-case catalog and record its allowed use | OWN-CLIN | OWN-CLIN | Demo review does not automatically make cases study-eligible. |
| GOV-004 | Versioned permission receipt; coded response capture; append-only corrections | OWN-ENG | OWN-ENG | OWN-DATA reviews fields; OWN-QA tests no save without valid permission for actual human responses. |
| GOV-005 | Expiry/withdrawal cleanup and export/backup inventory | OWN-DATA | OWN-ENG | OWN-PRIV reviews exceptions; OWN-QA verifies all linked content and derivative copies are handled. |
| GOV-006 | Persistence, restart, correction, export, privacy and deletion test report | OWN-QA | OWN-ENG | Failures remain visible; no claims of implemented controls from this document alone. |
| GOV-007 | Approve local demo readiness | OWN-PROJ | OWN-DATA | GOV-001–006 accepted; current scope only; no clinical/research deployment authorization. |
| GOV-008 | Later research protocol, consent and model-retirement plan | OWN-PROJ | OWN-METH | Deferred; designated investigator and required independent/institutional approvals before research capture. |

Recommended build order: GOV-001 and GOV-003 alongside software work using fabricated responses; GOV-002 before permission text is offered to real participants; GOV-004–006 to implement and verify it; GOV-007 before actual physician-response testing under this permission. GOV-008 remains out of scope.

## 8. Implementation checks

The JSON records approved demo documents and policy choices. It is not a complete
runtime governance record: null operator fields, unaccepted roles and pending
checks remain unresolved. Incorporation does not manufacture approvals for those
facts or automatically enable participant capture.

- Do not activate real physician-response capture while required operator/contact/appointment fields are unresolved, policy status is draft, or necessary review is missing. Continue synthetic QA with fabricated answers instead.
- Display an unselected Agree/Decline choice, offer the exact notice to save, and permit questions through a functioning contact route. Do not present a checkbox as proof of formal research consent compliance. [S3]
- Bind responses to permission receipt, case snapshot/version, original submission time, and collection purpose. Declining creates no response record.
- Keep names/crosswalks, real response data, exports, local databases, private role contact registers, and credentials outside Git. Use fabricated replacements in screenshots and bug reports. A `.gitignore` is not an access-control system.
- Ensure no training, network analytics, cloud backup, external AI call, hosted deployment, patient-system link, or real clinical recommendation is enabled.
- Withdrawal disables new capture/use pending verification; authorized cleanup respects earlier scheduled expiry, handles all linked revisions, and leaves only a minimal receipt. Verify requests reasonably; a public/guessable code is not sufficient proof of identity.
- Retention clocks do not restart on export, correction, restore, or policy revision. Each export expires when its earliest contained record expires.
- Confirm no need for indefinite identity linkage. Small sample sizes can be identifiable without names; no anonymity guarantee.
- Explicitly test and report limits of backup removal, local files, journals, and device deletion. Stop representing controls as active when tests fail.
- Keep all research reuse, named twin deployment, and commercial/data-sharing permissions false. New consent does not automatically legalize prior collection or extend expiring data.

## 9. Sources and boundaries

The legal/regulatory background is U.S.-focused. It is not a determination that this operator is a covered entity, that every Common Rule provision applies, that a particular institution oversees this project, or that the project is exempt. Verify applicable institutional, state, sponsor, FDA, international, and contractual requirements before changing the scope. No Florida/UF affiliation is assumed.

[S1] HHS/OHRP, *Coded Private Information or Biospecimens Used in Research, Guidance (2018)*. https://www.hhs.gov/ohrp/coded-private-information-or-biospecimens-used-research.html

[S2] HHS/OHRP, *Investigator Responsibilities FAQs* (record retention, consent documentation, and appropriate review). https://www.hhs.gov/ohrp/regulations-and-policy/guidance/faq/investigator-responsibilities/index.html

[S3] HHS/OHRP, *Informed Consent FAQs*. https://www.hhs.gov/ohrp/regulations-and-policy/guidance/faq/informed-consent/index.html

[S4] HHS/OHRP, *Withdrawal of Subjects from Research Guidance (2010)*, page last reviewed June 2, 2026. HHS notes the guidance predates the revised Common Rule but continues to reflect general thinking; do not rely on its old section numbering or continuing-review statements for current requirements. https://www.hhs.gov/ohrp/regulations-and-policy/guidance/guidance-on-withdrawal-of-subject/index.html

[S5] HHS/OCR, *Does the HIPAA Privacy Rule require covered entities to keep patients' medical records for any period of time?* https://www.hhs.gov/hipaa/for-professionals/faq/580/does-hipaa-require-covered-entities-to-keep-medical-records-for-any-period/index.html

[S6] HHS/OCR, *Summary of the HIPAA Security Rule*, last reviewed August 7, 2026. https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html

The source documents report sources checked September 9, 2026. This approval
revision does not claim a new source review. Demo retention periods are now
approved project policy choices, not numbers obtained from these sources or
universal legal minimums. Future-research periods remain deferred proposals.

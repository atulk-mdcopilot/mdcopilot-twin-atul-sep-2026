"""Governance gates use fabricated appointments and temporary databases only."""

import hashlib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from helpers import latest_version, values

from twin_lab.governance import Governance
from twin_lab.governance_schema import CONTROL_FLAGS, RETENTION_DAYS, ROLES
from twin_lab.schemas import Conflict, NotFound, ValidationError
from twin_lab.store import Store


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "governance.sqlite3"
        self.store = Store(self.path)
        self.governance = getattr(self.store, "governance", None) or Governance(self.store)
        self.version = latest_version(self.store.catalog.overview())

    @staticmethod
    def draft(**changes):
        body = {
            "request_id": str(uuid4()),
            "based_on_governance_id": None,
            "title": "Fabricated governance test",
            "status": "draft",
            "operator": {
                "legal_name": "",
                "project_contact": "",
                "privacy_contact": "",
                "pilot_close_date": "",
            },
            "permission": {"version": "", "text": ""},
            "retention": {"version": "", **dict.fromkeys(RETENTION_DAYS)},
            "owners": [],
            "approved_by_code": "",
            "approval_note": "",
            "controls": {
                "actor_code": "",
                "checked_at": "",
                "evidence": "",
                **dict.fromkeys(CONTROL_FLAGS, False),
            },
        }
        body.update(changes)
        return body

    def approved_body(self, **changes):
        timestamp = datetime.now(timezone.utc).isoformat()
        body = self.draft(
            status="approved",
            operator={
                "legal_name": "Fabricated operator",
                "project_contact": "test@example.invalid",
                "privacy_contact": "privacy@example.invalid",
                "pilot_close_date": (date.today() + timedelta(days=20)).isoformat(),
            },
            permission={
                "version": "TEST-PERM-1",
                "text": "  Fabricated permission notice. Café.\n  ",
            },
            retention={"version": "TEST-RET-1", **dict.fromkeys(RETENTION_DAYS, 7)},
            owners=[
                {
                    "role_code": role,
                    "actor_code": "STF-QA",
                    "person_name": "Fabricated test actor",
                    "contact": "actor@example.invalid",
                    "accepted_at": timestamp,
                }
                for role in ROLES
            ],
            controls={
                "actor_code": "STF-QA",
                "checked_at": timestamp,
                "evidence": "Fabricated test evidence only.",
                **dict.fromkeys(CONTROL_FLAGS, True),
            },
            approved_by_code="STF-QA",
            approval_note="Fabricated review determination, not actual approval.",
        )
        body.update(changes)
        return body

    def create_plan(self):
        protocol, _ = self.store.collection.save_protocol(
            {
                "request_id": str(uuid4()),
                "based_on_protocol_id": None,
                "title": "Synthetic test plan",
                "owner_code": "STF-QA",
                "physician_codes": ["PHY-QA", "PHY-OTHER"],
                "consent_statement": "Old draft plan text is not permission.",
                "consent_version": "DRAFT",
                "retention_days": None,
                "backup_owner_code": "",
                "backup_frequency": "manual_before_changes",
                "backup_retention_days": None,
                "notes": "Fabricated test data.",
            }
        )
        assignment, _ = self.store.collection.assign(
            {
                "request_id": str(uuid4()),
                "protocol_id": protocol["protocol_id"],
                "physician_code": "PHY-QA",
                "version_id": self.version["version_id"],
                "notes": "Fabricated assignment.",
            }
        )
        return protocol, assignment

    def record_review(self, disposition="approved", supersedes=None):
        return self.store.catalog.add_review(
            {
                "request_id": str(uuid4()),
                "version_id": self.version["version_id"],
                "reviewer_code": "STF-QA",
                "reviewed_on": date.today().isoformat(),
                "comments": "Fabricated clinical review for tests.",
                "disposition": disposition,
                "supersedes_review_id": supersedes,
            }
        )[0]

    def permission_body(self, governance, choice="agree", **changes):
        body = {
            "request_id": str(uuid4()),
            "governance_id": governance["governance_id"],
            "physician_code": "PHY-QA",
            "choice": choice,
        }
        body.update(changes)
        return body

    def setup_human(self):
        governance, _ = self.governance.save(self.approved_body())
        protocol, assignment = self.create_plan()
        review = self.record_review()
        receipt, _ = self.governance.permission(self.permission_body(governance))
        return governance, protocol, assignment, review, receipt

    def authorize(self, receipt, assignment, **changes):
        args = {
            "mode": "physician_demo",
            "receipt_id": receipt["receipt_id"],
            "code": "PHY-QA",
            "assignment_id": assignment["assignment_id"],
            "protocol_id": assignment["protocol_id"],
            "version_id": assignment["version_id"],
        }
        args.update(changes)
        with self.store.connection() as db:
            return self.governance.authorize(db, **args)

    def test_empty_database_is_not_approved_and_seeds_no_decisions(self):
        result = self.governance.overview()
        self.assertEqual(result["history"], [])
        self.assertEqual(result["receipts"], [])
        self.assertEqual(result["readiness"]["missing_fields"], ["governance"])
        self.assertFalse(result["readiness"]["actual_physician_capture_enabled"])
        self.assertFalse(result["readiness"]["study_collection_enabled"])
        saved, _ = self.governance.save(self.draft())
        self.assertTrue(all(saved["retention"][key] is None for key in RETENTION_DAYS))
        self.assertEqual(saved["owners"], [])
        with self.store.connection() as db:
            self.assertEqual(
                self.governance.authorize(db, "fabricated_qa")["capture_mode"], "fabricated_qa"
            )
            for mode in (None, "study", "legacy_unclassified"):
                with self.subTest(mode=mode), self.assertRaises(ValidationError):
                    self.governance.authorize(db, mode)
            with self.assertRaises(ValidationError):
                self.governance.authorize(db, "fabricated_qa", receipt_id=str(uuid4()))

    def test_draft_retries_are_idempotent_and_stale_changes_conflict(self):
        body = self.draft()
        first, duplicate = self.governance.save(body)
        self.assertFalse(duplicate)
        again, duplicate = Governance(Store(self.path)).save(body)
        self.assertTrue(duplicate)
        self.assertEqual(again, first)
        with self.assertRaises(Conflict):
            self.governance.save(dict(body, title="Changed retry"))
        second, _ = self.governance.save(self.draft(based_on_governance_id=first["governance_id"]))
        with self.assertRaises(Conflict):
            self.governance.save(self.draft(based_on_governance_id=first["governance_id"]))
        self.assertEqual(self.governance.overview()["history"], [first, second])

    def test_concurrent_governance_revisions_do_not_fork_history(self):
        first, _ = self.governance.save(self.draft())
        requests = [
            self.draft(based_on_governance_id=first["governance_id"], title=title)
            for title in ("A", "B")
        ]

        def attempt(body):
            try:
                return self.governance.save(body)[0]
            except Conflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, requests))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_approval_requires_operator_owners_review_retention_and_controls(self):
        missing = [self.draft(status="approved")]
        for field in ("operator", "permission", "retention", "controls"):
            for key in self.approved_body()[field]:
                body = self.approved_body()
                body[field][key] = (
                    False if key in CONTROL_FLAGS else None if key in RETENTION_DAYS else ""
                )
                missing.append(body)
        for key in ("actor_code", "person_name", "contact", "accepted_at"):
            body = self.approved_body()
            body["owners"][0][key] = ""
            missing.append(body)
        missing.extend(
            [
                self.approved_body(owners=[]),
                self.approved_body(approved_by_code="OTHER"),
                self.approved_body(approval_note=" "),
            ]
        )
        for body in missing:
            with self.subTest(body=body), self.assertRaises(ValidationError):
                self.governance.save(body)
        self.assertEqual(self.governance.overview()["history"], [])

    def test_malformed_fields_and_unapproved_scope_flags_are_rejected(self):
        invalid = [
            self.draft(training_allowed=True),
            self.draft(status="study"),
            self.draft(owners=[{}]),
        ]
        for value in (True, 0, 1.5, 3651, "30"):
            body = self.draft()
            body["retention"]["response_days"] = value
            invalid.append(body)
        for value in ("2026-01-01", (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()):
            body = self.draft()
            body["controls"]["checked_at"] = value
            invalid.append(body)
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(ValidationError):
                self.governance.save(body)

    def test_permission_requires_current_approved_notice_and_listed_code(self):
        draft, _ = self.governance.save(self.draft())
        with self.assertRaises(Conflict):
            self.governance.permission(self.permission_body(draft))
        approved, _ = self.governance.save(
            self.approved_body(based_on_governance_id=draft["governance_id"])
        )
        with self.assertRaises(Conflict):
            self.governance.permission(self.permission_body(approved))
        self.create_plan()
        with self.assertRaises(Conflict):
            self.governance.permission(self.permission_body(approved, physician_code="UNLISTED"))
        with self.assertRaises(Conflict):
            self.governance.permission(self.permission_body(draft))
        for choice in (None, "", True, "yes"):
            with self.subTest(choice=choice), self.assertRaises(ValidationError):
                self.governance.permission(self.permission_body(approved, choice=choice))

    def test_exact_permission_copy_hash_retry_and_restart(self):
        approved, _, assignment, _, receipt = self.setup_human()
        self.assertEqual(receipt["permission_text"], approved["permission"]["text"])
        self.assertEqual(receipt["permission_version"], approved["permission"]["version"])
        self.assertEqual(
            receipt["permission_sha256"],
            hashlib.sha256(receipt["permission_text"].encode()).hexdigest(),
        )
        self.assertEqual(Governance(Store(self.path)).receipt(receipt["receipt_id"]), receipt)
        body = {
            key: receipt[key] for key in ("request_id", "governance_id", "physician_code", "choice")
        }
        saved, duplicate = self.governance.permission(body)
        self.assertTrue(duplicate)
        self.assertEqual(saved, receipt)
        with self.assertRaises(Conflict):
            self.governance.permission(dict(body, choice="decline"))
        result = self.authorize(receipt, assignment)
        self.assertEqual(result["governance_id"], approved["governance_id"])
        self.assertEqual(result["permission_sha256"], receipt["permission_sha256"])
        for key in ("training_allowed", "research_reuse_allowed", "public_release_allowed"):
            self.assertIs(result[key], False)
        self.assertNotIn("owners", result)
        self.assertNotIn("operator", result)

    def test_decline_records_no_response_and_invalidates_earlier_agreement(self):
        approved, _, assignment, _, agreed = self.setup_human()
        declined, _ = self.governance.permission(self.permission_body(approved, choice="decline"))
        self.assertEqual(self.store.responses(), [])
        for receipt in (agreed, declined):
            with self.subTest(receipt=receipt["choice"]), self.assertRaises(Conflict):
                self.authorize(receipt, assignment)

    def test_new_agreement_supersedes_receipt_without_overwriting(self):
        approved, _, assignment, _, first = self.setup_human()
        second, _ = self.governance.permission(self.permission_body(approved))
        with self.assertRaises(Conflict):
            self.authorize(first, assignment)
        self.authorize(second, assignment)
        self.assertEqual(self.governance.receipt(first["receipt_id"]), first)

    def test_draft_revision_and_revocation_close_gate_but_leave_exact_receipts(self):
        approved, _, assignment, _, receipt = self.setup_human()
        draft, _ = self.governance.save(
            self.draft(based_on_governance_id=approved["governance_id"])
        )
        with self.assertRaises(Conflict):
            self.authorize(receipt, assignment)
        revoked, _ = self.governance.save(
            self.draft(
                based_on_governance_id=draft["governance_id"],
                status="revoked",
                approved_by_code="STF-QA",
                approval_note="Fabricated suspension.",
            )
        )
        self.assertFalse(
            self.governance.overview()["readiness"]["actual_physician_capture_enabled"]
        )
        self.assertEqual(self.governance.receipt(receipt["receipt_id"]), receipt)
        with self.assertRaises(Conflict):
            self.governance.permission(self.permission_body(revoked))

    def test_new_approved_revision_requires_new_permission_and_new_text_version(self):
        approved, _, assignment, _, receipt = self.setup_human()
        changed = self.approved_body(based_on_governance_id=approved["governance_id"])
        changed["permission"]["text"] += "Changed notice."
        with self.assertRaises(Conflict):
            self.governance.save(changed)
        changed["permission"]["version"] = "TEST-PERM-2"
        revised, _ = self.governance.save(changed)
        with self.assertRaises(Conflict):
            self.authorize(receipt, assignment)
        latest, _ = self.governance.permission(self.permission_body(revised))
        self.authorize(latest, assignment)

    def test_human_capture_requires_current_approved_pinned_assignment(self):
        approved, _, assignment, review, receipt = self.setup_human()
        for changes in (
            {"code": "PHY-OTHER"},
            {"assignment_id": None},
            {"version_id": str(uuid4())},
            {"protocol_id": str(uuid4())},
        ):
            with self.subTest(changes=changes), self.assertRaises(Conflict):
                self.authorize(receipt, assignment, **changes)
        self.record_review("needs_revision", review["review_id"])
        with self.assertRaises(Conflict):
            self.authorize(receipt, assignment)

    def test_missing_receipt_and_unknown_receipt_fail(self):
        with self.store.connection() as db:
            with self.assertRaises(ValidationError):
                self.governance.authorize(db, "physician_demo")
            with self.assertRaises(NotFound):
                self.governance.authorize(db, "physician_demo", receipt_id=str(uuid4()))

    def test_withdrawal_blocks_both_new_permission_and_response_capture(self):
        approved, _, assignment, _, receipt = self.setup_human()
        presentation = self.store.present(
            assignment_id=assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )
        self.store.lifecycle.withdraw(
            {"request_id": str(uuid4()), "physician_code": "PHY-QA", "actor_code": "STF-QA"}
        )
        with self.assertRaises(Conflict):
            self.authorize(receipt, assignment)
        with self.assertRaises(Conflict):
            self.governance.permission(self.permission_body(approved))
        with self.assertRaises(Conflict):
            self.store.submit(presentation["presentation_id"], values(physician_code="PHY-QA"))

    def test_policy_change_after_presentation_blocks_submission(self):
        approved, _, assignment, _, receipt = self.setup_human()
        presentation = self.store.present(
            assignment_id=assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )
        self.governance.save(self.approved_body(based_on_governance_id=approved["governance_id"]))
        with self.assertRaises(Conflict):
            self.store.submit(presentation["presentation_id"], values(physician_code="PHY-QA"))
        self.assertEqual(self.store.responses(), [])

    def test_sql_updates_and_deletes_cannot_overwrite_governance_or_permission(self):
        self.setup_human()
        for table in ("governance_versions", "permission_receipts"):
            for operation in (f"UPDATE {table} SET payload = '{{}}'", f"DELETE FROM {table}"):
                with self.subTest(operation=operation), self.assertRaises(sqlite3.IntegrityError):
                    with self.store.connection() as db:
                        db.execute(operation)


if __name__ == "__main__":
    unittest.main()

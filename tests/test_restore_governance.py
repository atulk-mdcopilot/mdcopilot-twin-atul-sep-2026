"""Restoring older approval or permission never silently reopens human capture."""

import sqlite3
import unittest
from uuid import uuid4

from helpers import values
import test_governance as governance_tests
from twin_lab.schemas import Conflict, canonical_json, now
from twin_lab.store import Store


class RestoreGovernanceTests(unittest.TestCase):
    setUp = governance_tests.GovernanceTests.setUp
    draft = staticmethod(governance_tests.GovernanceTests.draft)
    approved_body = governance_tests.GovernanceTests.approved_body
    create_plan = governance_tests.GovernanceTests.create_plan
    record_review = governance_tests.GovernanceTests.record_review
    permission_body = governance_tests.GovernanceTests.permission_body
    setup_human = governance_tests.GovernanceTests.setup_human
    authorize = governance_tests.GovernanceTests.authorize

    def barrier(self, timestamp=None):
        record = {"restore_id": str(uuid4()), "restored_at": timestamp or now()}
        with self.store.connection() as db:
            db.execute("INSERT INTO restore_barriers VALUES (?, ?)",
                       (record["restore_id"], canonical_json(record)))
        return record

    def test_restore_requires_new_approval_and_permission_without_changing_history(self):
        governance, _, assignment, _, receipt = self.setup_human()
        self.barrier()
        restarted = Store(self.path)
        overview = restarted.governance.overview()
        self.assertEqual(overview["history"], [governance])
        self.assertEqual(overview["receipts"], [receipt])
        self.assertIn("restore_reapproval_required", overview["readiness"]["missing_fields"])
        self.assertFalse(overview["readiness"]["actual_physician_capture_enabled"])
        with self.assertRaises(Conflict):
            self.authorize(receipt, assignment)
        with self.assertRaises(Conflict):
            self.governance.permission(self.permission_body(governance))
        updated, _ = self.governance.save(self.approved_body(based_on_governance_id=governance["governance_id"]))
        self.assertTrue(self.governance.overview()["readiness"]["actual_physician_capture_enabled"])
        with self.assertRaises(Conflict):
            self.authorize(receipt, assignment)
        latest, _ = self.governance.permission(self.permission_body(updated))
        presentation = self.store.present(assignment_id=assignment["assignment_id"], capture_mode="physician_demo",
                                          permission_receipt_id=latest["receipt_id"])
        response, _ = self.store.submit(presentation["presentation_id"], values(physician_code="PHY-QA"))
        self.assertEqual(response["permission_receipt_id"], latest["receipt_id"])
        self.assertEqual(self.governance.receipt(receipt["receipt_id"]), receipt)

    def test_draft_or_identical_retry_does_not_approve_restored_capture(self):
        body = self.approved_body()
        governance, _ = self.governance.save(body)
        self.barrier()
        same, duplicate = self.governance.save(body)
        self.assertTrue(duplicate)
        self.assertEqual(same, governance)
        self.assertFalse(self.governance.overview()["readiness"]["actual_physician_capture_enabled"])
        self.governance.save(self.draft(based_on_governance_id=governance["governance_id"]))
        readiness = self.governance.overview()["readiness"]
        self.assertFalse(readiness["actual_physician_capture_enabled"])
        self.assertIn("approved_governance", readiness["missing_fields"])

    def test_equal_timestamp_and_subsequent_restore_both_require_reapproval(self):
        governance, _, assignment, _, receipt = self.setup_human()
        self.barrier(governance["created_at"])
        with self.assertRaises(Conflict):
            self.authorize(receipt, assignment)
        updated, _ = self.governance.save(self.approved_body(based_on_governance_id=governance["governance_id"]))
        latest, _ = self.governance.permission(self.permission_body(updated))
        self.authorize(latest, assignment)
        self.barrier()
        with self.assertRaises(Conflict):
            self.authorize(latest, assignment)

    def test_restore_barrier_is_immutable_and_fabricated_qa_still_available(self):
        self.barrier()
        with self.store.connection() as db:
            metadata = self.governance.authorize(db, "fabricated_qa")
        self.assertEqual(metadata["capture_mode"], "fabricated_qa")
        for statement in ("UPDATE restore_barriers SET payload='{}'", "DELETE FROM restore_barriers"):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                with self.store.connection() as db:
                    db.execute(statement)


if __name__ == "__main__":
    unittest.main()

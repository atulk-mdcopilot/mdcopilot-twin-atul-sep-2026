"""Filesystem boundaries retain restrictions even when SQLite rolls back."""

import hashlib
import json
import sqlite3
import unittest
from uuid import uuid4

import test_governance as governance_tests
import test_lifecycle as lifecycle_tests
from helpers import values
from process_helpers import ChildBarrier

from twin_lab.lifecycle_files import append_ledger, restore_snapshot
from twin_lab.schemas import Conflict, ValidationError
from twin_lab.store import Store


class FileInterruptions(unittest.TestCase):
    setUp = lifecycle_tests.LifecycleTests.setUp
    response = lifecycle_tests.LifecycleTests.response

    def raw_responses(self):
        with sqlite3.connect(self.path) as db:
            return list(db.execute("SELECT id,payload FROM responses ORDER BY rowid"))

    def test_backup_after_durable_rename_recovers_same_snapshot_and_manifest(self):
        original = self.response()
        body = {"request_id": str(uuid4())}
        child = ChildBarrier(self, self.path, "backup_before_manifest", {"body": body})
        child.kill_at_boundary()
        path = self.path.parent / "backups" / f"twin-lab-{body['request_id']}.sqlite3"
        saved_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        saved_mtime = path.stat().st_mtime_ns
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM local_backups").fetchone()[0], 0)
        # A later live change must not be swept into the recovered earlier snapshot.
        later = self.response(code="LATER_TEST")
        restarted = Store(self.path)
        recovered, duplicate = restarted.collection.backup(body)
        self.assertFalse(duplicate)
        self.assertEqual(recovered["sha256"], saved_hash)
        self.assertEqual(recovered["source_root_ids"], [original["response_id"]])
        self.assertEqual(path.stat().st_mtime_ns, saved_mtime)
        self.assertNotIn(later["response_id"], recovered["source_root_ids"])
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            frozen = json.loads(db.execute("SELECT payload FROM response_lifecycle").fetchone()[0])
            self.assertEqual(frozen["retention_anchor_at"], original["submitted_at"])
        retry, duplicate = Store(self.path).collection.backup(body)
        self.assertTrue(duplicate)
        self.assertEqual(retry, recovered)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), saved_hash)

    def prepare_disposal(self):
        first = self.response()
        correction = self.response(previous=first)
        exports = [self.lifecycle.managed_export(self.store.export())[1] for _ in range(2)]
        before = self.raw_responses()
        self.timestamp = "2026-12-31T12:00:00+00:00"
        plan = self.lifecycle.plan_disposal()
        self.assertEqual(plan["eligible_root_ids"], [first["response_id"]])
        self.assertEqual(set(plan["export_ids"]), {item["export_id"] for item in exports})
        return first, correction, exports, before, plan

    def assert_disposal_recovery(self, original, expected_root):
        restarted = Store(self.path)
        restarted.lifecycle.clock = lambda: self.timestamp
        self.assertEqual(self.raw_responses(), original)
        self.assertEqual(restarted.responses(), [])
        self.assertEqual(restarted.export()["responses"], [])
        first_entry = restarted.lifecycle.ledger_path.read_text().splitlines()[0]
        self.assertEqual(json.loads(first_entry)["root_ids"], [expected_root])
        # Recovery requires reviewing the current plan after the interruption.
        fresh = restarted.lifecycle.plan_disposal()
        result = restarted.lifecycle.apply_disposal(fresh, "FAULT_TEST")
        self.assertEqual(result["disposed_root_ids"], [expected_root])
        self.assertEqual(self.raw_responses(), [])
        self.assertEqual(Store(self.path).export()["responses"], [])
        self.assertEqual(restarted.lifecycle.ledger_path.read_text().splitlines()[0], first_entry)
        self.assertFalse(result["forensic_erasure_claimed"])

    def test_disposal_journal_before_purge_blocks_rollback_content_until_recovery(self):
        first, _, _, before, plan = self.prepare_disposal()
        child = ChildBarrier(
            self,
            self.path,
            "disposal_after_journal",
            {
                "plan": plan,
                "clock": self.timestamp,
            },
        )
        child.kill_at_boundary()
        self.assert_disposal_recovery(before, first["response_id"])

    def test_cleanup_unlink_before_commit_keeps_whole_chain_restricted(self):
        first, _, exports, before, plan = self.prepare_disposal()
        first_export = self.path.parent / "exports" / exports[0]["filename"]
        child = ChildBarrier(
            self,
            self.path,
            "disposal_during_cleanup",
            {
                "plan": plan,
                "clock": self.timestamp,
                "filename": first_export.name,
            },
        )
        child.kill_at_boundary()
        self.assertFalse(first_export.exists())
        self.assertTrue((self.path.parent / "exports" / exports[1]["filename"]).exists())
        self.assert_disposal_recovery(before, first["response_id"])
        self.assertFalse(any((self.path.parent / "exports").glob("*.json")))


class RestoreInterruptions(unittest.TestCase):
    def setUp(self):
        self.fixture = governance_tests.GovernanceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store, self.path = self.fixture.store, self.fixture.path
        _, _, self.assignment, _, self.receipt = self.fixture.setup_human()
        presentation = self.store.present(
            assignment_id=self.assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=self.receipt["receipt_id"],
        )
        response, _ = self.store.submit(
            presentation["presentation_id"], values(physician_code="PHY-QA")
        )
        self.response_id = response["response_id"]
        backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        self.source = self.path.parent / "backups" / backup["filename"]
        self.source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.live_bytes = self.path.read_bytes()
        # This invented authoritative entry is a restore fixture, not an actual disposal.
        append_ledger(
            self.store.lifecycle.ledger_path,
            {
                "entry_id": str(uuid4()),
                "root_ids": [self.response_id],
                "deleted_at": "2026-09-12T12:00:00+00:00",
                "actor_code": "FAULT_TEST",
            },
        )

    def assert_sanitized(self, path):
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM responses").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM presentations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM restore_barriers").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        restored = Store(path)
        self.assertEqual(restored.export()["responses"], [])
        self.assertIn(
            "restore_reapproval_required",
            restored.governance.overview()["readiness"]["missing_fields"],
        )
        with self.assertRaises(Conflict):
            restored.present(
                assignment_id=self.assignment["assignment_id"],
                capture_mode="physician_demo",
                permission_receipt_id=self.receipt["receipt_id"],
            )
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)
        self.assertEqual(self.path.read_bytes(), self.live_bytes)

    def test_restore_before_publish_has_no_destination_and_recovers_sanitized_copy(self):
        destination = self.path.parent / "restore-before" / "restored.sqlite3"
        child = ChildBarrier(
            self,
            self.path,
            "restore_before_publish",
            {
                "source": self.source,
                "destination": destination,
            },
        )
        child.kill_at_boundary()
        self.assertFalse(destination.exists())
        temporary = list(destination.parent.glob(".restore-*.sqlite3"))
        self.assertEqual(len(temporary), 1)
        with sqlite3.connect(temporary[0]) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM responses").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM restore_barriers").fetchone()[0], 1)
        restore_snapshot(self.source, destination, self.store.lifecycle.ledger_path)
        self.assert_sanitized(destination)

    def test_restore_after_publish_is_sanitized_and_existing_destination_not_replaced(self):
        destination = self.path.parent / "restore-after" / "restored.sqlite3"
        child = ChildBarrier(
            self,
            self.path,
            "restore_after_publish",
            {
                "source": self.source,
                "destination": destination,
            },
        )
        child.kill_at_boundary()
        self.assertTrue(destination.is_file())
        before = destination.read_bytes()
        with self.assertRaises(ValidationError):
            restore_snapshot(self.source, destination, self.store.lifecycle.ledger_path)
        self.assertEqual(destination.read_bytes(), before)
        self.assert_sanitized(destination)

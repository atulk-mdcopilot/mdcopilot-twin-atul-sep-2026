"""Lifecycle acceptance tests use invented responses and temporary storage only."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import shutil
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

from helpers import values
from twin_lab.lifecycle import expiry, instant
from twin_lab.lifecycle_files import append_ledger, ledger_entries, restore_snapshot
from twin_lab.schemas import Conflict, ValidationError, canonical_json
from twin_lab.store import Store


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.store = Store(self.path)
        self.lifecycle = self.store.lifecycle
        self.timestamp = "2026-09-10T12:00:00+00:00"
        self.lifecycle.clock = lambda: self.timestamp
        self.governance = {"governance_id": str(uuid4()), "operator": {"pilot_close_date": "2026-09-30"},
            "retention": {"version": "TEST_ONLY", "response_days": 90, "after_close_days": 30,
                "export_days": 30, "backup_days": 30, "backup_after_deletion_days": 30,
                "withdrawal_days": 30, "permission_after_close_days": 365, "audit_after_close_days": 365}}

    def response(self, previous=None, governed=True, submitted_at=None, code="TEST_CODE"):
        # Direct synthetic fixtures isolate lifecycle behavior from permission UI tests.
        case = self.store.cases()[0]
        presentation_id, response_id = str(uuid4()), str(uuid4())
        record = {"response_id": response_id, "presentation_id": presentation_id,
                  "supersedes_response_id": previous["response_id"] if previous else None,
                  "physician_code": code, "submitted_at": submitted_at or self.timestamp,
                  "presented_at": self.timestamp, "case_id": case["case_id"],
                  "case_snapshot": case, "original_values": values(physician_code=code),
                  "normalized_values": values(physician_code=code),
                  "capture_mode": "physician_demo" if governed else "fabricated_qa"}
        presentation = {"presentation_id": presentation_id,
                        "supersedes_response_id": record["supersedes_response_id"]}
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO presentations VALUES (?,?)", (presentation_id, canonical_json(presentation)))
            db.execute("INSERT INTO responses VALUES (?,?,?,?)", (response_id, presentation_id,
                record["supersedes_response_id"], canonical_json(record)))
            self.lifecycle.attach(db, record, self.governance if governed else None,
                                  str(uuid4()) if governed else None)
        return record

    def withdrawal(self, code="TEST_CODE"):
        return self.lifecycle.withdraw({"request_id": str(uuid4()), "physician_code": code,
                                        "actor_code": "TEST_CUSTODIAN"})[0]

    def verify(self, withdrawal, days=None):
        return self.lifecycle.verify_withdrawal({"request_id": str(uuid4()),
            "withdrawal_id": withdrawal["withdrawal_id"], "actor_code": "TEST_CUSTODIAN",
            "verification_attested": True, "withdrawal_days": days})[0]

    def test_expiry_uses_original_anchor_and_earlier_pilot_deadline(self):
        self.assertEqual(expiry(self.timestamp, self.governance), "2026-10-30T23:59:59.999999+00:00")
        self.assertEqual(expiry("2026-01-01T00:00:00+00:00", self.governance), "2026-04-01T00:00:00+00:00")
        first = self.response()
        correction = self.response(previous=first, submitted_at="2026-10-01T12:00:00+00:00")
        with self.store.connection() as db:
            self.assertEqual(self.lifecycle.metadata(db, first["response_id"]),
                             self.lifecycle.metadata(db, correction["response_id"]))
        self.assertEqual(len(self.lifecycle.overview()["records"]), 1)

    def test_expired_records_are_not_ordinary_review_export_or_correction(self):
        response = self.response(submitted_at="2026-01-01T00:00:00+00:00")
        self.assertEqual(self.store.responses(), [])
        self.assertEqual(self.store.export()["responses"], [])
        self.assertIn(response["response_id"], self.lifecycle.plan_disposal()["eligible_root_ids"])
        with self.store.connection() as db:
            self.assertEqual(len(db.execute("SELECT id FROM responses").fetchall()), 1)

    def test_unknown_existing_records_are_preserved_without_policy_adoption(self):
        response = self.response(governed=False)
        with self.store.connection() as db:
            db.execute("DROP TRIGGER response_lifecycle_no_DELETE")
            db.execute("DELETE FROM response_lifecycle")
        overview = Store(self.path).lifecycle.overview()
        record = overview["records"][0]
        self.assertEqual(record["permission_status"], "unknown_legacy")
        self.assertIsNone(record["expires_at"])
        self.assertIn(response["response_id"], overview["disposal"]["unknown_policy_root_ids"])
        self.assertEqual(overview["disposal"]["eligible_root_ids"], [])

    def test_withdrawal_stops_use_and_capture_immediately_before_verification(self):
        response = self.response()
        snapshot = self.store.export()
        body = {"request_id": str(uuid4()), "physician_code": "TEST_CODE", "actor_code": "TEST_STAFF"}
        first, duplicate = self.lifecycle.withdraw(body)
        self.assertFalse(duplicate)
        self.assertEqual(self.lifecycle.withdraw(body), (first, True))
        with self.assertRaises(Conflict):
            self.lifecycle.withdraw(dict(body, physician_code="OTHER_CODE"))
        self.assertEqual(self.store.responses(), [])
        with self.store.connection() as db:
            with self.assertRaises(Conflict):
                self.lifecycle.require_capture(db, "TEST_CODE")
            self.assertEqual(self.lifecycle.restriction(db, response["response_id"]), "withdrawn")
        with self.assertRaises(Conflict):
            self.lifecycle.managed_export(snapshot)
        self.assertEqual(self.lifecycle.plan_disposal()["eligible_root_ids"], [])

    def test_verification_does_not_extend_expiry_and_legacy_requires_explicit_days(self):
        response = self.response(submitted_at="2026-06-15T00:00:00+00:00")
        verified = self.verify(self.withdrawal())
        self.assertEqual(verified["deadlines"][response["response_id"]], "2026-09-13T00:00:00+00:00")
        self.response(governed=False, code="LEGACY")
        withdrawal = self.withdrawal("LEGACY")
        with self.assertRaises(ValidationError):
            self.verify(withdrawal)
        receipt = self.verify(withdrawal, days=7)
        self.assertEqual(next(iter(receipt["deadlines"].values())), "2026-09-17T12:00:00+00:00")

    def test_hold_blocks_normal_use_and_purge_until_authorized_release(self):
        response = self.response(submitted_at="2026-01-01T00:00:00+00:00")
        old_plan = self.lifecycle.plan_disposal()
        hold, _ = self.lifecycle.hold({"request_id": str(uuid4()), "response_ids": [response["response_id"]],
            "actor_code": "TEST_STAFF", "authority_record": "Synthetic authority reference"})
        plan = self.lifecycle.plan_disposal()
        self.assertEqual(plan["eligible_root_ids"], [])
        self.assertEqual(plan["held_root_ids"], [response["response_id"]])
        with self.assertRaises(Conflict):
            self.lifecycle.apply_disposal(old_plan, "TEST_STAFF")
        self.lifecycle.release_hold({"request_id": str(uuid4()), "hold_id": hold["hold_id"],
            "actor_code": "TEST_STAFF", "authority_record": "Synthetic release reference"})
        self.assertEqual(self.lifecycle.plan_disposal()["eligible_root_ids"], [response["response_id"]])

    def test_disposal_removes_whole_chain_and_pending_correction_presentations(self):
        original = self.response(submitted_at="2026-01-01T00:00:00+00:00")
        self.response(previous=original)
        pending = str(uuid4())
        with self.store.connection() as db:
            db.execute("INSERT INTO presentations VALUES (?,?)", (pending, canonical_json(
                {"supersedes_response_id": original["response_id"], "case_snapshot": "Synthetic only"})))
        result = self.lifecycle.apply_disposal(self.lifecycle.plan_disposal(), "TEST_STAFF")
        self.assertEqual(result["disposed_root_ids"], [original["response_id"]])
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM responses").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM presentations").fetchone()[0], 0)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            triggers = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
            self.assertIn("responses_no_DELETE", triggers)
            self.assertIn("presentations_no_DELETE", triggers)
        self.assertEqual(ledger_entries(self.lifecycle.ledger_path)[0]["root_ids"], [original["response_id"]])
        self.assertNotIn("next_action", self.lifecycle.ledger_path.read_text())

    def test_failed_database_purge_rolls_back_and_journal_blocks_reuse(self):
        original = self.response(submitted_at="2026-01-01T00:00:00+00:00")
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER test_disposal_failure BEFORE DELETE ON responses BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.lifecycle.apply_disposal(self.lifecycle.plan_disposal(), "TEST_STAFF")
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM responses").fetchone()[0], 1)
            self.assertEqual(self.lifecycle.restriction(db, original["response_id"]), "disposal_recorded")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM responses")
            db.execute("DROP TRIGGER test_disposal_failure")
        self.lifecycle.apply_disposal(self.lifecycle.plan_disposal(), "TEST_STAFF")

    def test_old_backup_restore_reapplies_deletions_before_exposing_new_file(self):
        original = self.response(submitted_at="2026-01-01T00:00:00+00:00")
        self.response(previous=original)
        backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        source = self.path.parent / "detached-old-backup.sqlite3"
        shutil.copyfile(self.path.parent / "backups" / backup["filename"], source)
        self.lifecycle.apply_disposal(self.lifecycle.plan_disposal(), "TEST_STAFF")
        destination = self.path.parent / "restore" / "restored.sqlite3"
        result = restore_snapshot(source, destination, self.lifecycle.ledger_path)
        self.assertEqual(result["integrity_check"], "ok")
        with sqlite3.connect(destination) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM responses").fetchone()[0], 0)
        with self.assertRaises(ValidationError):
            restore_snapshot(source, destination, self.lifecycle.ledger_path)

    def test_old_backup_restore_also_reapplies_pending_withdrawal_and_hold(self):
        withdrawn = self.response()
        held = self.response(code="HELD_CODE")
        backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        self.withdrawal()
        self.lifecycle.hold({"request_id": str(uuid4()), "response_ids": [held["response_id"]],
            "actor_code": "TEST_STAFF", "authority_record": "Synthetic hold"})
        source = self.path.parent / "backups" / backup["filename"]
        destination = self.path.parent / "restore" / "restored.sqlite3"
        restore_snapshot(source, destination, self.lifecycle.ledger_path)
        restored = Store(destination)
        self.assertEqual(restored.responses(), [])
        with restored.connection() as db:
            self.assertEqual(restored.lifecycle.restriction(db, withdrawn["response_id"]), "withdrawn")
            self.assertEqual(restored.lifecycle.restriction(db, held["response_id"]), "legal_hold")

    def test_managed_export_inventory_and_expiry_preserve_original_age(self):
        response = self.response(submitted_at="2026-06-15T00:00:00+00:00")
        exported, manifest = self.lifecycle.managed_export(self.store.export())
        self.assertTrue(manifest["filename"].startswith("twin-lab-export-"))
        self.assertEqual(manifest["expires_at"], "2026-09-13T00:00:00+00:00")
        path = self.path.parent / "exports" / manifest["filename"]
        self.assertEqual(json.loads(path.read_text()), exported)
        self.assertEqual(manifest["source_root_ids"], [response["response_id"]])
        self.withdrawal()
        self.assertIs(self.lifecycle.overview()["exports"][0]["usable"], False)
        self.timestamp = "2026-09-13T00:00:00+00:00"
        plan = self.lifecycle.plan_disposal()
        self.assertIn(manifest["export_id"], plan["export_ids"])
        self.lifecycle.apply_disposal(plan, "TEST_STAFF")
        self.assertFalse(path.exists())

    def test_backup_deadline_cannot_reset_source_expiry(self):
        response = self.response(submitted_at="2026-06-15T00:00:00+00:00")
        backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        expected = min(instant(backup["created_at"]) + timedelta(days=30),
                       datetime(2026, 10, 13, tzinfo=timezone.utc))
        self.assertEqual(instant(backup["expires_at"]), expected)
        self.assertEqual(backup["source_backup_grace_days"], {response["response_id"]: 30})
        self.timestamp = "2026-11-01T00:00:00+00:00"
        self.assertIn(backup["backup_id"], self.lifecycle.plan_disposal()["backup_ids"])

    def test_malformed_ledger_fails_closed_and_missing_ledger_cannot_restore(self):
        self.response()
        self.lifecycle.ledger_path.write_text("interrupted", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.store.responses()
        with self.assertRaises(ValidationError):
            restore_snapshot(self.path, self.path.parent / "restore.sqlite3", self.path.parent / "missing.jsonl")

    def test_missing_journal_is_not_silently_recreated_on_restart(self):
        self.response()
        (self.path.parent / "lifecycle-events.jsonl").unlink()
        with self.assertRaises(RuntimeError):
            Store(self.path)
        with self.assertRaises(RuntimeError):
            self.store.responses()

    def test_disposal_without_durable_ledger_cannot_delete_response(self):
        self.response(submitted_at="2026-01-01T00:00:00+00:00")
        with patch("twin_lab.lifecycle_files.append_ledger", side_effect=OSError("Synthetic disk full")):
            with self.assertRaises(OSError):
                self.lifecycle.apply_disposal(self.lifecycle.plan_disposal(), "TEST_STAFF")
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM responses").fetchone()[0], 1)

    def test_failed_withdrawal_database_write_still_blocks_use_and_retries_safely(self):
        self.response()
        body = {"request_id": str(uuid4()), "physician_code": "TEST_CODE", "actor_code": "TEST_STAFF"}
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER test_event_failure BEFORE INSERT ON lifecycle_events BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.lifecycle.withdraw(body)
        self.assertEqual(self.store.responses(), [])
        with self.store.connection() as db:
            db.execute("DROP TRIGGER test_event_failure")
        receipt, _ = self.lifecycle.withdraw(body)
        self.assertEqual(receipt["physician_code"], "TEST_CODE")
        self.assertEqual(len(self.lifecycle.overview()["withdrawals"]), 1)

    def test_held_sources_protect_expired_managed_copies(self):
        response = self.response(submitted_at="2026-06-15T00:00:00+00:00")
        _, exported = self.lifecycle.managed_export(self.store.export())
        backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        self.lifecycle.hold({"request_id": str(uuid4()), "response_ids": [response["response_id"]],
            "actor_code": "TEST_STAFF", "authority_record": "Synthetic hold"})
        self.timestamp = "2026-11-01T00:00:00+00:00"
        plan = self.lifecycle.plan_disposal()
        self.assertNotIn(exported["export_id"], plan["export_ids"])
        self.assertNotIn(backup["backup_id"], plan["backup_ids"])

    def test_unmanaged_copies_are_visible_and_never_automatically_disposed(self):
        directory = self.path.parent / "backups"
        directory.mkdir()
        path = directory / "unknown-old-copy.sqlite3"
        path.write_bytes(b"Synthetic test sentinel")
        plan = self.lifecycle.plan_disposal()
        self.assertEqual(plan["unmanaged_copy_filenames"]["backups"], [path.name])
        self.assertEqual(plan["backup_ids"], [])
        self.lifecycle.apply_disposal(plan, "TEST_STAFF")
        self.assertTrue(path.exists())

    def test_verification_retry_after_disposal_returns_original_receipt(self):
        self.response(submitted_at="2026-01-01T00:00:00+00:00")
        withdrawal = self.withdrawal()
        body = {"request_id": str(uuid4()), "withdrawal_id": withdrawal["withdrawal_id"],
                "actor_code": "TEST_STAFF", "verification_attested": True, "withdrawal_days": None}
        saved, _ = self.lifecycle.verify_withdrawal(body)
        self.lifecycle.apply_disposal(self.lifecycle.plan_disposal(), "TEST_STAFF")
        self.assertEqual(self.lifecycle.verify_withdrawal(body), (saved, True))
        with self.assertRaises(Conflict):
            self.lifecycle.verify_withdrawal(dict(body, withdrawal_days=7))

    def test_hold_retry_after_release_and_disposal_keeps_original_record(self):
        response = self.response(submitted_at="2026-01-01T00:00:00+00:00")
        body = {"request_id": str(uuid4()), "response_ids": [response["response_id"]],
                "actor_code": "TEST_STAFF", "authority_record": "Synthetic authority"}
        saved, _ = self.lifecycle.hold(body)
        self.lifecycle.release_hold({"request_id": str(uuid4()), "hold_id": saved["hold_id"],
            "actor_code": "TEST_STAFF", "authority_record": "Synthetic release"})
        self.lifecycle.apply_disposal(self.lifecycle.plan_disposal(), "TEST_STAFF")
        self.assertEqual(self.lifecycle.hold(body), (saved, True))

    def test_structurally_invalid_journals_fail_with_safe_errors(self):
        self.response()
        for path, payload in ((self.lifecycle.ledger_path, '{"root_ids":null}'),
                              (self.path.parent / "lifecycle-events.jsonl", '[]')):
            before = path.read_bytes()
            try:
                path.write_text(payload, encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    self.store.responses()
            finally:
                path.write_bytes(before)

    def test_retried_disposal_cannot_restart_backup_grace(self):
        response = self.response()
        backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        # An early verified removal followed by crash recovery must keep the first
        # removal anchor, even if a later authorizing receipt is also present.
        for timestamp in ("2026-08-01T00:00:00+00:00", "2026-09-10T00:00:00+00:00"):
            append_ledger(self.lifecycle.ledger_path, {"entry_id": str(uuid4()),
                "root_ids": [response["response_id"]], "deleted_at": timestamp,
                "actor_code": "TEST_STAFF", "plan_confirmation": "Synthetic fixture"})
        manifest = next(row for row in self.lifecycle.overview()["backups"] if row["backup_id"] == backup["backup_id"])
        self.assertEqual(manifest["expires_at"], "2026-08-31T00:00:00+00:00")

    def test_verify_restored_withdrawal_preserves_scope_when_snapshot_predates_some_roots(self):
        present = self.response()
        backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        absent = self.response()
        withdrawal = self.withdrawal()
        destination = self.path.parent / "restore-partial" / "restored.sqlite3"
        restore_snapshot(self.path.parent / "backups" / backup["filename"], destination,
                         self.lifecycle.ledger_path)
        restored = Store(destination)
        restored.lifecycle.clock = lambda: self.timestamp
        verified, _ = restored.lifecycle.verify_withdrawal({"request_id": str(uuid4()),
            "withdrawal_id": withdrawal["withdrawal_id"], "actor_code": "TEST_STAFF",
            "verification_attested": True, "withdrawal_days": None})
        self.assertEqual(verified["unavailable_root_ids"], [absent["response_id"]])
        self.assertEqual(verified["deadlines"], {present["response_id"]: "2026-10-10T12:00:00+00:00"})
        self.assertEqual(restored.lifecycle.overview()["withdrawals"][0]["root_ids"], withdrawal["root_ids"])

    def test_verify_pending_withdrawal_after_one_chain_has_already_expired_and_been_disposed(self):
        expired = self.response(submitted_at="2026-01-01T00:00:00+00:00")
        remaining = self.response()
        withdrawal = self.withdrawal()
        self.lifecycle.apply_disposal(self.lifecycle.plan_disposal(), "TEST_STAFF")
        verified = self.verify(withdrawal)
        self.assertEqual(verified["unavailable_root_ids"], [expired["response_id"]])
        self.assertEqual(verified["deadlines"], {remaining["response_id"]: "2026-10-10T12:00:00+00:00"})
        self.assertEqual(self.lifecycle.overview()["withdrawals"][0]["root_ids"], withdrawal["root_ids"])

    def restored_after_partial_verification(self, governed=True, days=None):
        first = self.response()
        early, _ = self.store.collection.backup({"request_id": str(uuid4())})
        second = self.response(governed=governed)
        later, _ = self.store.collection.backup({"request_id": str(uuid4())})
        withdrawal = self.withdrawal()
        partial_path = self.path.parent / "partial-verified" / "restored.sqlite3"
        restore_snapshot(self.path.parent / "backups" / early["filename"], partial_path,
                         self.lifecycle.ledger_path)
        partial = Store(partial_path)
        partial.lifecycle.clock = lambda: self.timestamp
        verification, _ = partial.lifecycle.verify_withdrawal({"request_id": str(uuid4()),
            "withdrawal_id": withdrawal["withdrawal_id"], "actor_code": "TEST_STAFF",
            "verification_attested": True, "withdrawal_days": days})
        full_path = self.path.parent / "later-restored" / "restored.sqlite3"
        restore_snapshot(self.path.parent / "backups" / later["filename"], full_path,
                         partial.lifecycle.ledger_path)
        full = Store(full_path)
        return first, second, verification, full

    def test_later_restore_does_not_restart_verified_withdrawal_clock_for_previously_absent_root(self):
        first, second, original, restored = self.restored_after_partial_verification()
        before = restored.lifecycle.plan_disposal("2026-10-10T11:59:59+00:00")
        self.assertNotIn(second["response_id"], before["eligible_root_ids"])
        due = restored.lifecycle.plan_disposal("2026-10-10T12:00:00+00:00")
        self.assertEqual(due["eligible_root_ids"], sorted([first["response_id"], second["response_id"]]))
        self.assertEqual(restored.lifecycle.overview()["verifications"][0], original)

    def test_later_legacy_restore_uses_only_explicit_period_from_original_verification(self):
        _, second, original, restored = self.restored_after_partial_verification(governed=False, days=7)
        self.assertEqual(original["withdrawal_days"], 7)
        self.assertNotIn(second["response_id"], restored.lifecycle.plan_disposal(
            "2026-09-17T11:59:59+00:00")["eligible_root_ids"])
        self.assertIn(second["response_id"], restored.lifecycle.plan_disposal(
            "2026-09-17T12:00:00+00:00")["eligible_root_ids"])

    def test_later_legacy_restore_with_no_chosen_period_stays_manual_review(self):
        _, second, _, restored = self.restored_after_partial_verification(governed=False)
        plan = restored.lifecycle.plan_disposal("2026-12-01T12:00:00+00:00")
        self.assertNotIn(second["response_id"], plan["eligible_root_ids"])
        self.assertIn(second["response_id"], plan["unknown_policy_root_ids"])


if __name__ == "__main__":
    unittest.main()

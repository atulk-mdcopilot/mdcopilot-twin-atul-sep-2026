"""Narrow synthetic I/O failures; no host disk filling or actual data paths."""

import hashlib
import json
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_file_interruptions as file_tests

from twin_lab.lifecycle_files import restore_snapshot
from twin_lab.schemas import ValidationError
from twin_lab.store import Store


class StorageIOErrors(unittest.TestCase):
    setUp = file_tests.FileInterruptions.setUp
    response = file_tests.FileInterruptions.response

    def manifest_count(self, table):
        # Test-owned constant table names only.
        with sqlite3.connect(self.path) as db:
            return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def test_backup_rename_error_removes_temporary_and_retry_creates_verified_copy(self):
        self.response()
        body = {"request_id": str(uuid4())}
        directory = self.path.parent / "backups"
        with patch("twin_lab.backups.os.replace", side_effect=OSError("Synthetic rename error")):
            with self.assertRaisesRegex(OSError, "Synthetic rename"):
                self.store.collection.backup(body)
        self.assertEqual(list(directory.iterdir()), [])
        self.assertEqual(self.manifest_count("local_backups"), 0)
        recovered, duplicate = Store(self.path).collection.backup(body)
        self.assertFalse(duplicate)
        self.assertEqual(
            hashlib.sha256((directory / recovered["filename"]).read_bytes()).hexdigest(),
            recovered["sha256"],
        )

    def test_backup_fsync_error_keeps_unconfirmed_snapshot_for_same_request_recovery(self):
        self.response()
        body = {"request_id": str(uuid4())}
        with patch("twin_lab.backups.os.fsync", side_effect=OSError("Synthetic fsync error")):
            with self.assertRaisesRegex(OSError, "Synthetic fsync"):
                self.store.collection.backup(body)
        path = self.path.parent / "backups" / f"twin-lab-{body['request_id']}.sqlite3"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.manifest_count("local_backups"), 0)
        recovered, duplicate = Store(self.path).collection.backup(body)
        self.assertFalse(duplicate)
        self.assertEqual(recovered["sha256"], before)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertEqual(self.manifest_count("local_backups"), 1)

    def test_export_fsync_error_cleans_copy_and_does_not_commit_manifest(self):
        self.response()
        with patch(
            "twin_lab.lifecycle_files.os.fsync", side_effect=OSError("Synthetic export fsync error")
        ):
            with self.assertRaisesRegex(OSError, "Synthetic export fsync"):
                self.lifecycle.managed_export(self.store.export())
        self.assertFalse(any((self.path.parent / "exports").iterdir()))
        self.assertEqual(self.manifest_count("managed_exports"), 0)
        restarted = Store(self.path)
        exported, manifest = restarted.lifecycle.managed_export(restarted.export())
        self.assertEqual(exported["response_count"], 1)
        self.assertTrue((self.path.parent / "exports" / manifest["filename"]).is_file())

    def test_journal_fsync_error_can_leave_restriction_and_retries_same_event(self):
        self.response()
        body = {
            "request_id": str(uuid4()),
            "physician_code": "TEST_CODE",
            "actor_code": "FAULT_TEST",
        }
        with patch(
            "twin_lab.lifecycle_files.os.fsync",
            side_effect=OSError("Synthetic journal fsync error"),
        ):
            with self.assertRaisesRegex(OSError, "Synthetic journal fsync"):
                self.lifecycle.withdraw(body)
        self.assertEqual(self.manifest_count("lifecycle_events"), 0)
        journal = self.path.parent / "lifecycle-events.jsonl"
        entry = json.loads(journal.read_text())
        restarted = Store(self.path)
        self.assertEqual(restarted.responses(), [])
        recovered, duplicate = restarted.lifecycle.withdraw(body)
        self.assertFalse(duplicate)
        self.assertEqual(recovered, entry["event"])
        self.assertEqual(len(journal.read_text().splitlines()), 1)
        self.assertEqual(self.manifest_count("lifecycle_events"), 1)


class RestoreIOErrors(unittest.TestCase):
    setUp = file_tests.RestoreInterruptions.setUp
    assert_sanitized = file_tests.RestoreInterruptions.assert_sanitized

    def test_publish_error_leaves_no_destination_and_retry_is_sanitized(self):
        destination = self.path.parent / "restore-link-error" / "restored.sqlite3"
        with patch(
            "twin_lab.lifecycle_restore.os.link", side_effect=OSError("Synthetic link error")
        ):
            with self.assertRaisesRegex(OSError, "Synthetic link"):
                restore_snapshot(self.source, destination, self.store.lifecycle.ledger_path)
        self.assertFalse(destination.exists())
        self.assertEqual(list(destination.parent.glob(".restore-*.sqlite3")), [])
        restore_snapshot(self.source, destination, self.store.lifecycle.ledger_path)
        self.assert_sanitized(destination)

    def test_sync_after_publication_error_preserves_sanitized_unconfirmed_destination(self):
        destination = self.path.parent / "restore-sync-error" / "restored.sqlite3"
        with patch(
            "twin_lab.lifecycle_restore.sync_directory",
            side_effect=OSError("Synthetic directory fsync error"),
        ):
            with self.assertRaisesRegex(OSError, "Synthetic directory fsync"):
                restore_snapshot(self.source, destination, self.store.lifecycle.ledger_path)
        self.assertTrue(destination.is_file())
        self.assert_sanitized(destination)
        with self.assertRaises(ValidationError):
            restore_snapshot(self.source, destination, self.store.lifecycle.ledger_path)
        recovery = self.path.parent / "restore-new-after-error" / "restored.sqlite3"
        restore_snapshot(self.source, recovery, self.store.lifecycle.ledger_path)
        self.assert_sanitized(recovery)

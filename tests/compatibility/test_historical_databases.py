"""Versioned byte preservation and restored-history characterization."""

import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import test_governance as governance_tests
from helpers import values
from historical_fixtures import historical_database, raw_rows

from twin_lab.lifecycle_restore import restore_snapshot
from twin_lab.schemas import Conflict, snapshot_hash
from twin_lab.store import Store


class HistoricalDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "historical.sqlite3"

    def assert_history_unchanged(self, before):
        after = raw_rows(self.path)
        for table, rows in before.items():
            with self.subTest(table=table):
                self.assertEqual(after[table][: len(rows)], rows)
                if table not in ("case_versions", "case_families"):
                    self.assertEqual(after[table], rows)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 4)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_empty_v0_initialization_restarts_without_new_identities_or_decisions(self):
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
        original = Store(self.path)
        catalog = original.catalog.overview()
        rows = raw_rows(self.path)
        journals = {path.name: path.read_bytes() for path in self.path.parent.glob("*.jsonl")}
        self.assertEqual(len(catalog["versions"]), 20)
        self.assertEqual(len(catalog["families"]), 5)
        for version in catalog["versions"]:
            self.assertEqual(snapshot_hash(version["snapshot"]), version["snapshot_sha256"])
        for _ in range(2):
            restarted = Store(self.path)
            self.assertEqual(raw_rows(self.path), rows)
            self.assertEqual(restarted.catalog.overview(), catalog)
            self.assertEqual(restarted.responses(), [])
            self.assertEqual(restarted.governance.overview()["history"], [])
            self.assertEqual(restarted.collection.overview()["history"], [])
            self.assertEqual(
                {path.name: path.read_bytes() for path in self.path.parent.glob("*.jsonl")},
                journals,
            )

    def test_v1_and_v2_original_bytes_links_timestamps_and_retry_survive_startup(self):
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                self.path = Path(directory) / "historical.sqlite3"
                responses, requests = historical_database(self.path, version)
                before = raw_rows(self.path)
                self.assertIn("Café".encode(), before["responses"][0][-1])
                self.assertIn(b"\n   ", before["responses"][0][-1])
                for _ in range(2):
                    store = Store(self.path)
                    self.assert_history_unchanged(before)
                    self.assertEqual(store.responses(), responses)
                    self.assertEqual(store.export()["responses"], responses)
                    for response in responses:
                        self.assertEqual(
                            store.submit(response["presentation_id"], response["original_values"]),
                            (response, True),
                        )
                        with store.connection() as db:
                            metadata = store.lifecycle.metadata(db, response["response_id"])
                        self.assertEqual(
                            metadata["retention_anchor_at"], responses[0]["submitted_at"]
                        )
                        self.assertEqual(metadata["permission_status"], "unknown_legacy")
                        self.assertIsNone(metadata["expires_at"])
                        self.assertIsNone(metadata["policy"])
                    self.assertEqual(
                        responses[1]["supersedes_response_id"], responses[0]["response_id"]
                    )
                    for name, method in (
                        ("review", store.catalog.add_review),
                        ("plan", store.collection.save_protocol),
                        ("assignment", store.collection.assign),
                    ):
                        if name in requests:
                            body, expected = requests[name]
                            self.assertEqual(method(body), (expected, True))
                            changed = dict(body, request_id=body["request_id"])
                            field = "comments" if name == "review" else "notes"
                            changed[field] += " Different retry."
                            with self.assertRaises(Conflict):
                                method(changed)
                    self.assert_history_unchanged(before)
                settled = raw_rows(self.path)
                Store(self.path)
                self.assertEqual(raw_rows(self.path), settled)

    def test_unknown_version_changes_neither_database_bytes_nor_files(self):
        historical_database(self.path, 2)
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA user_version = 99")
        original = self.path.read_bytes()
        paths = set(self.path.parent.iterdir())
        with self.assertRaisesRegex(RuntimeError, "Unsupported database version"):
            Store(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(set(self.path.parent.iterdir()), paths)


class VersionThreeHistoryTests(unittest.TestCase):
    setUp = governance_tests.GovernanceTests.setUp
    draft = staticmethod(governance_tests.GovernanceTests.draft)
    approved_body = governance_tests.GovernanceTests.approved_body
    create_plan = governance_tests.GovernanceTests.create_plan
    record_review = governance_tests.GovernanceTests.record_review
    permission_body = governance_tests.GovernanceTests.permission_body
    setup_human = governance_tests.GovernanceTests.setup_human

    def populated_history(self):
        governance, protocol, assignment, review, receipt = self.setup_human()
        presentation = self.store.present(
            assignment_id=assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )
        original, _ = self.store.submit(
            presentation["presentation_id"],
            values(physician_code="PHY-QA", rationale="Original café.\n"),
        )
        correction = self.store.present(
            supersedes_response_id=original["response_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )
        corrected, _ = self.store.submit(
            correction["presentation_id"],
            values(physician_code="PHY-QA", next_action="Fabricated correction."),
        )
        revised_snapshot = copy.deepcopy(self.version["snapshot"])
        revised_snapshot["version"] = "TEST-2.0"
        version_body = {
            "request_id": str(uuid4()),
            "based_on_version_id": self.version["version_id"],
            "version": "TEST-2.0",
            "editor_code": "STF-QA",
            "change_note": "Fabricated version with preserved request bytes. Café.\n",
            "snapshot": revised_snapshot,
        }
        version, _ = self.store.catalog.add_version(version_body)
        self.store.lifecycle.managed_export(self.store.export())
        backup_body = {"request_id": str(uuid4())}
        backup, _ = self.store.collection.backup(backup_body)
        hold_body = {
            "request_id": str(uuid4()),
            "response_ids": [corrected["response_id"]],
            "actor_code": "STF-QA",
            "authority_record": "Fabricated compatibility hold.",
        }
        hold, _ = self.store.lifecycle.hold(hold_body)
        withdraw_body = {
            "request_id": str(uuid4()),
            "physician_code": "PHY-QA",
            "actor_code": "STF-QA",
        }
        withdrawal, _ = self.store.lifecycle.withdraw(withdraw_body)
        verify_body = {
            "request_id": str(uuid4()),
            "withdrawal_id": withdrawal["withdrawal_id"],
            "actor_code": "STF-QA",
            "verification_attested": True,
            "withdrawal_days": None,
        }
        verification, _ = self.store.lifecycle.verify_withdrawal(verify_body)
        # These are exclusively legacy v1 contract records: retain an actual
        # version-3 starting marker even after the current runtime moves to v4.
        with self.store.connection() as db:
            db.execute("PRAGMA user_version = 3")
        return {
            "governance": governance,
            "protocol": protocol,
            "assignment": assignment,
            "review": review,
            "receipt": receipt,
            "responses": [original, corrected],
            "version": (version_body, version),
            "backup": (backup_body, backup),
            "hold": (hold_body, hold),
            "withdraw": (withdraw_body, withdrawal),
            "verify_withdrawal": (verify_body, verification),
        }

    def test_v3_all_domain_history_and_frozen_policy_survive_repeated_startup(self):
        history = self.populated_history()
        before = raw_rows(self.path)
        journals = {path.name: path.read_bytes() for path in self.path.parent.glob("*.jsonl")}
        with self.store.connection() as db:
            anchor = copy.deepcopy(
                self.store.lifecycle.metadata(db, history["responses"][0]["response_id"])
            )
        self.assertEqual(anchor["retention_anchor_at"], history["responses"][0]["submitted_at"])
        self.assertIsNotNone(anchor["expires_at"])
        self.assertEqual(anchor["policy"], history["governance"]["retention"])
        for _ in range(2):
            restarted = Store(self.path)
            self.assertEqual(raw_rows(self.path), before)
            self.assertEqual(restarted.responses(), [])
            self.assertEqual(restarted.export()["responses"], [])
            self.assertEqual(restarted.governance.overview()["receipts"], [history["receipt"]])
            for response in history["responses"]:
                with restarted.connection() as db:
                    self.assertEqual(
                        restarted.lifecycle.metadata(db, response["response_id"]), anchor
                    )
                    self.assertEqual(
                        restarted.lifecycle.restriction(db, response["response_id"]), "legal_hold"
                    )
                with self.assertRaises(Conflict):
                    restarted.submit(response["presentation_id"], response["original_values"])
            for name in ("hold", "withdraw", "verify_withdrawal"):
                body, expected = history[name]
                self.assertEqual(getattr(restarted.lifecycle, name)(body), (expected, True))
            body, expected = history["backup"]
            self.assertEqual(restarted.collection.backup(body), (expected, True))
            body, expected = history["version"]
            self.assertEqual(restarted.catalog.add_version(body), (expected, True))
            self.assertEqual(raw_rows(self.path), before)
            self.assertEqual(
                {path.name: path.read_bytes() for path in self.path.parent.glob("*.jsonl")},
                journals,
            )

    def test_restored_v3_bytes_and_restrictions_survive_repeated_startup(self):
        history = self.populated_history()
        final_backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        source = self.path.parent / "backups" / final_backup["filename"]
        before = raw_rows(source)
        destination = self.path.parent / "restored" / "historical.sqlite3"
        restore_snapshot(source, destination, self.store.lifecycle.ledger_path)
        restored_rows = raw_rows(destination)
        for table, rows in before.items():
            with self.subTest(table=table):
                if table != "restore_barriers":
                    self.assertEqual(restored_rows[table], rows)
        self.assertEqual(len(restored_rows["restore_barriers"]), 1)
        for _ in range(2):
            restored = Store(destination)
            self.assertEqual(raw_rows(destination), restored_rows)
            self.assertEqual(restored.responses(), [])
            self.assertEqual(restored.export()["responses"], [])
            self.assertIn(
                "restore_reapproval_required",
                restored.governance.overview()["readiness"]["missing_fields"],
            )
            for response in history["responses"]:
                with restored.connection() as db:
                    self.assertEqual(
                        restored.lifecycle.restriction(db, response["response_id"]), "legal_hold"
                    )
                    metadata = restored.lifecycle.metadata(db, response["response_id"])
                    self.assertEqual(
                        metadata["retention_anchor_at"], history["responses"][0]["submitted_at"]
                    )
            # The old source snapshot and authoritative journals are read-only inputs.
            self.assertEqual(raw_rows(source), before)


if __name__ == "__main__":
    unittest.main()

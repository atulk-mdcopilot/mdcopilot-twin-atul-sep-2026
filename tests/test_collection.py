"""Draft rules, pinned assignments, and local backup acceptance tests."""

import hashlib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from uuid import uuid4

from helpers import latest_version, values
from twin_lab.schemas import ValidationError
from twin_lab.store import Conflict, NotFound, Store


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "collection.sqlite3"
        self.store = Store(self.path)
        self.version = latest_version(self.store.catalog.overview())

    def protocol_body(self, **changes):
        body = {
            "request_id": str(uuid4()), "based_on_protocol_id": None,
            "title": "Synthetic software test plan", "owner_code": "TEST_OWNER",
            "physician_codes": ["DEMO_01", "DEMO_02"],
            "consent_statement": "Synthetic test string, not an actual consent statement.",
            "consent_version": "TEST_ONLY", "retention_days": 7,
            "backup_owner_code": "TEST_BACKUP", "backup_frequency": "manual_before_changes",
            "backup_retention_days": 7, "notes": "Temporary test data only.",
        }
        body.update(changes)
        return body

    def assignment_body(self, protocol, **changes):
        body = {
            "request_id": str(uuid4()), "protocol_id": protocol["protocol_id"],
            "physician_code": "DEMO_01", "version_id": self.version["version_id"],
            "notes": "Synthetic assignment for software tests.",
        }
        body.update(changes)
        return body

    def test_blank_governance_values_stay_incomplete_and_study_disabled(self):
        body = self.protocol_body(owner_code="", physician_codes=[], consent_statement="",
            consent_version="", retention_days=None, backup_owner_code="", backup_retention_days=None)
        protocol, duplicate = self.store.collection.save_protocol(body)
        self.assertFalse(duplicate)
        self.assertEqual(protocol["consent_statement"], "")
        self.assertIsNone(protocol["retention_days"])
        self.assertEqual(protocol["backup_owner_code"], "")
        overview = Store(self.path).collection.overview()
        self.assertEqual(overview["current"], protocol)
        for field in ("owner_code", "physician_codes", "consent_statement", "consent_version",
                      "retention_days", "backup_owner_code", "backup_retention_days"):
            self.assertIn(field, overview["readiness"]["missing_fields"])
        self.assertIs(overview["readiness"]["configuration_complete"], False)
        self.assertIs(overview["readiness"]["study_collection_enabled"], False)
        self.assertEqual(protocol["collection_purpose"], "demo")
        self.assertIs(protocol["study_collection_enabled"], False)
        self.assertEqual(protocol["assignment_strategy"], "manual_version_pinned")

    def test_protocol_retry_preserves_history_and_rejects_stale_edits(self):
        body = self.protocol_body()
        first, duplicate = self.store.collection.save_protocol(body)
        self.assertFalse(duplicate)
        same, duplicate = Store(self.path).collection.save_protocol(body)
        self.assertTrue(duplicate)
        self.assertEqual(same, first)
        with self.assertRaises(Conflict):
            self.store.collection.save_protocol(dict(body, notes="Changed retry"))
        second, _ = self.store.collection.save_protocol(self.protocol_body(
            based_on_protocol_id=first["protocol_id"], title="Revised synthetic plan"))
        with self.assertRaises(Conflict):
            self.store.collection.save_protocol(self.protocol_body(based_on_protocol_id=first["protocol_id"]))
        overview = Store(self.path).collection.overview()
        self.assertEqual(overview["history"], [first, second])
        self.assertEqual(overview["current"], second)

    def test_consent_text_is_preserved_exactly_and_whitespace_is_incomplete(self):
        statement = "  Synthetic test consent wording: café.\n  "
        version = "  TEST-é-1  "
        protocol, _ = self.store.collection.save_protocol(self.protocol_body(
            consent_statement=statement, consent_version=version))
        self.assertEqual(protocol["consent_statement"], statement)
        self.assertEqual(protocol["consent_version"], version)
        self.assertEqual(self.store.export()["collection_protocols"][0]["consent_statement"], statement)
        self.store.collection.save_protocol(self.protocol_body(
            based_on_protocol_id=protocol["protocol_id"], consent_statement=" \n\t ", consent_version=" "))
        missing = self.store.collection.overview()["readiness"]["missing_fields"]
        self.assertIn("consent_statement", missing)
        self.assertIn("consent_version", missing)

    def test_concurrent_protocol_edits_cannot_fork_history(self):
        first, _ = self.store.collection.save_protocol(self.protocol_body())
        bodies = [self.protocol_body(based_on_protocol_id=first["protocol_id"], notes=note)
                  for note in ("Left synthetic edit", "Right synthetic edit")]

        def attempt(body):
            try:
                return self.store.collection.save_protocol(body)[0]
            except Conflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, bodies))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(len(self.store.collection.overview()["history"]), 2)

    def test_invalid_protocols_cannot_enable_study_or_record_invalid_rules(self):
        invalid = (
            {"study_collection_enabled": True}, {"collection_purpose": "study"},
            {"eligible_for_study": True}, {"title": ""}, {"retention_days": 0},
            {"retention_days": True}, {"retention_days": 3651}, {"retention_days": 1.5},
            {"backup_retention_days": -1}, {"backup_frequency": "automatic_cloud"},
            {"physician_codes": ["DEMO_01", "DEMO_01"]},
            {"physician_codes": ["name@example.test"]}, {"owner_code": "bad code"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.store.collection.save_protocol(self.protocol_body(**changes))
        self.assertEqual(self.store.collection.overview()["history"], [])

    def test_assignments_require_listed_code_and_existing_protocol_and_version(self):
        protocol, _ = self.store.collection.save_protocol(self.protocol_body())
        for changes, error in (
            ({"physician_code": "UNKNOWN"}, Conflict),
            ({"version_id": str(uuid4())}, NotFound),
            ({"protocol_id": str(uuid4())}, NotFound),
            ({"study_collection_enabled": True}, ValidationError),
        ):
            with self.subTest(changes=changes), self.assertRaises(error):
                self.store.collection.assign(self.assignment_body(protocol, **changes))
        self.assertEqual(self.store.collection.overview()["assignments"], [])

    def test_assignment_retries_are_idempotent_and_changed_retry_conflicts(self):
        protocol, _ = self.store.collection.save_protocol(self.protocol_body())
        body = self.assignment_body(protocol)
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: self.store.collection.assign(body), range(3)))
        self.assertEqual(len({record["assignment_id"] for record, _ in results}), 1)
        self.assertEqual(sum(not duplicate for _, duplicate in results), 1)
        with self.assertRaises(Conflict):
            self.store.collection.assign(dict(body, physician_code="DEMO_02"))
        self.assertEqual(len(Store(self.path).collection.overview()["assignments"]), 1)

    def test_assignment_pins_rules_version_and_code_through_response_correction(self):
        first, _ = self.store.collection.save_protocol(self.protocol_body())
        assignment, _ = self.store.collection.assign(self.assignment_body(first))
        self.store.collection.save_protocol(self.protocol_body(
            based_on_protocol_id=first["protocol_id"], physician_codes=["DEMO_02"]))
        presentation = self.store.present(assignment_id=assignment["assignment_id"], capture_mode="fabricated_qa", qa_acknowledged=True)
        with self.assertRaises(Conflict):
            self.store.submit(presentation["presentation_id"], values(physician_code="DEMO_02"))
        response, _ = self.store.submit(presentation["presentation_id"], values())
        self.assertEqual(response["assignment_id"], assignment["assignment_id"])
        self.assertEqual(response["protocol_id"], first["protocol_id"])
        self.assertEqual(response["case_version_id"], self.version["version_id"])
        self.assertEqual(response["response_schema_version"], "1.2")
        self.assertEqual(response["collection_purpose"], "demo")
        self.assertIs(response["eligible_for_study"], False)
        correction = self.store.present(supersedes_response_id=response["response_id"], capture_mode="fabricated_qa", qa_acknowledged=True)
        corrected, _ = self.store.submit(correction["presentation_id"], values(next_action="Corrected"))
        for field in ("assignment_id", "protocol_id", "case_version_id", "case_review_id"):
            self.assertEqual(response[field], corrected[field])

    def test_unapproved_assignment_is_visible_without_enabling_collection(self):
        protocol, _ = self.store.collection.save_protocol(self.protocol_body())
        assignment, _ = self.store.collection.assign(self.assignment_body(protocol))
        readiness = self.store.collection.overview()["readiness"]
        self.assertEqual(readiness["missing_fields"], [])
        self.assertIn(assignment["assignment_id"], readiness["unapproved_assignment_ids"])
        self.assertIs(readiness["configuration_complete"], False)
        self.assertIs(readiness["study_collection_enabled"], False)
        self.store.catalog.add_review({"request_id": str(uuid4()),
            "version_id": self.version["version_id"], "reviewer_code": "TEST_REVIEWER",
            "reviewed_on": date.today().isoformat(), "comments": "Synthetic software test only.",
            "disposition": "approved", "supersedes_review_id": None})
        complete = self.store.collection.overview()["readiness"]
        self.assertIs(complete["configuration_complete"], True)
        self.assertEqual(complete["unapproved_assignment_ids"], [])
        self.assertIs(complete["study_collection_enabled"], False)

    @staticmethod
    def database_contents(path):
        with sqlite3.connect(path) as db:
            names = [row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            return {name: db.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
                    for name in names if name != "local_backups"}

    def test_verified_backup_restores_all_data_into_separate_database(self):
        protocol, _ = self.store.collection.save_protocol(self.protocol_body())
        assignment, _ = self.store.collection.assign(self.assignment_body(protocol))
        presentation = self.store.present(assignment_id=assignment["assignment_id"], capture_mode="fabricated_qa", qa_acknowledged=True)
        self.store.submit(presentation["presentation_id"], values())
        before = self.database_contents(self.path)
        request = {"request_id": str(uuid4())}
        backup, duplicate = self.store.collection.backup(request)
        self.assertFalse(duplicate)
        backup_path = self.path.parent / "backups" / backup["filename"]
        self.assertEqual(backup_path.parent, self.path.parent / "backups")
        self.assertTrue(backup_path.is_file())
        self.assertEqual(backup["size_bytes"], backup_path.stat().st_size)
        self.assertEqual(backup["sha256"], hashlib.sha256(backup_path.read_bytes()).hexdigest())
        restored_path = self.path.parent / "separate-restore" / "restored.sqlite3"
        restored_path.parent.mkdir()
        from twin_lab.lifecycle_files import restore_snapshot
        restore_snapshot(backup_path, restored_path, self.store.lifecycle.ledger_path)
        with sqlite3.connect(restored_path) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        restored_contents = self.database_contents(restored_path)
        self.assertEqual(len(restored_contents.pop("restore_barriers")), 1)
        before.pop("restore_barriers")
        self.assertEqual(restored_contents, before)
        restored = Store(restored_path)
        self.assertEqual(restored.responses(), self.store.responses())
        self.assertEqual(restored.catalog.overview(), self.store.catalog.overview())
        for key in ("current", "history", "assignments", "readiness"):
            self.assertEqual(restored.collection.overview()[key], self.store.collection.overview()[key])
        retried, duplicate = Store(self.path).collection.backup(request)
        self.assertTrue(duplicate)
        self.assertEqual(retried, backup)
        self.assertEqual(len(list(backup_path.parent.iterdir())), 1)

    def test_backup_cannot_write_to_client_chosen_path(self):
        with self.assertRaises(ValidationError):
            self.store.collection.backup({"request_id": str(uuid4()), "path": "../outside.sqlite3"})
        self.assertEqual(self.store.collection.overview()["backups"], [])


if __name__ == "__main__":
    unittest.main()

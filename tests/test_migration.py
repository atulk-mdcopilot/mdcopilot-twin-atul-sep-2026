"""Upgrade actual v1-shaped SQLite records without rewriting saved payloads."""

import copy
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from helpers import FIXTURES, latest_version, values
from twin_lab.catalog import Catalog
from twin_lab.schemas import snapshot_hash
from twin_lab.store import Store


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "legacy.sqlite3"
        snapshot = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        self.presentation = {
            "presentation_id": str(uuid4()), "presented_at": "2026-09-08T12:00:00.000000+00:00",
            "case_snapshot": snapshot, "snapshot_sha256": snapshot_hash(snapshot),
            "supersedes_response_id": None,
        }
        original = values(rationale=" Legacy Unicode: café.\n")
        self.response = {
            "response_id": str(uuid4()), "presentation_id": self.presentation["presentation_id"],
            "physician_code": "DEMO_01", "case_id": snapshot["case_id"],
            "case_family": snapshot["family_id"], "case_version": snapshot["version"],
            "response_schema_version": "1.0", "case_snapshot": snapshot,
            "snapshot_sha256": self.presentation["snapshot_sha256"],
            "presented_at": self.presentation["presented_at"],
            "submitted_at": "2026-09-08T12:01:00.000000+00:00",
            "original_values": original,
            "normalized_values": {key: value.strip() if isinstance(value, str) else value
                                  for key, value in original.items()},
            "ai_advice_shown": False, "collection_purpose": "demo",
            "case_review_status": "unreviewed", "eligible_for_study": False,
            "supersedes_response_id": None,
        }
        self.presentation_text = json.dumps(self.presentation, ensure_ascii=False, indent=2)
        self.response_text = json.dumps(self.response, ensure_ascii=False, indent=2)
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE presentations (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE responses (
                    id TEXT PRIMARY KEY,
                    presentation_id TEXT NOT NULL UNIQUE REFERENCES presentations(id),
                    supersedes_id TEXT UNIQUE REFERENCES responses(id),
                    payload TEXT NOT NULL
                );
                PRAGMA user_version = 1;
            """)
            db.execute("INSERT INTO presentations VALUES (?, ?)",
                       (self.presentation["presentation_id"], self.presentation_text))
            db.execute("INSERT INTO responses VALUES (?, ?, ?, ?)",
                       (self.response["response_id"], self.presentation["presentation_id"],
                        None, self.response_text))

    def test_v1_upgrade_retains_exact_payload_bytes_and_exports_original_schema(self):
        store = Store(self.path)
        self.assertEqual(store.responses(), [self.response])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT payload FROM responses").fetchone()[0], self.response_text)
            self.assertEqual(db.execute("SELECT payload FROM presentations").fetchone()[0], self.presentation_text)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        exported = store.export()
        self.assertEqual(exported["export_schema_version"], "1.2")
        self.assertEqual(exported["responses"], [self.response])
        self.assertEqual(exported["responses"][0]["response_schema_version"], "1.0")
        self.assertNotIn("case_version_id", exported["responses"][0])
        self.assertEqual(len(exported["case_versions"]), 20)
        self.assertEqual(len(exported["case_families"]), 5)
        for field in ("case_reviews", "collection_protocols", "assignments"):
            self.assertEqual(exported[field], [])
        restarted = Store(self.path)
        self.assertEqual(restarted.responses(), [self.response])
        self.assertEqual(restarted.catalog.overview(), store.catalog.overview())

    def test_correction_of_legacy_response_preserves_original_and_exact_snapshot(self):
        original = copy.deepcopy(self.response)
        store = Store(self.path)
        presentation = store.present(supersedes_response_id=original["response_id"], capture_mode="legacy_unclassified")
        correction, duplicate = store.submit(presentation["presentation_id"], values(next_action="Legacy correction"))
        self.assertFalse(duplicate)
        self.assertEqual(correction["case_snapshot"], original["case_snapshot"])
        self.assertEqual(correction["snapshot_sha256"], original["snapshot_sha256"])
        self.assertEqual(correction["supersedes_response_id"], original["response_id"])
        self.assertEqual(correction["response_schema_version"], "1.2")
        self.assertEqual(correction["capture_mode"], "legacy_unclassified")
        self.assertIsNone(correction["permission_receipt_id"])
        self.assertEqual(store.responses(), [original, correction])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT payload FROM responses WHERE id=?",
                (original["response_id"],)).fetchone()[0], self.response_text)

    def test_migrated_observations_remain_append_only(self):
        Store(self.path)
        for operation in ("UPDATE responses SET payload='{}'", "DELETE FROM responses",
                          "UPDATE presentations SET payload='{}'", "DELETE FROM presentations"):
            with self.subTest(operation=operation):
                with sqlite3.connect(self.path) as db, self.assertRaises(sqlite3.DatabaseError):
                    db.execute(operation)
        self.assertEqual(Store(self.path).responses(), [self.response])

    def test_unsupported_database_version_is_rejected_without_rewriting_payload(self):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA user_version = 99")
        with self.assertRaises(RuntimeError):
            Store(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 99)
            self.assertEqual(db.execute("SELECT payload FROM responses").fetchone()[0], self.response_text)


class WordingMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "before-wording.sqlite3"
        with patch.object(Catalog, "_seed_wording_revision"):
            self.store = Store(self.path)
        self.original_catalog = self.store.catalog.overview()
        self.assertEqual(len(self.original_catalog["versions"]), 10)

    def payload_rows(self):
        tables = ("presentations", "responses", "case_versions", "case_reviews",
                  "case_families", "collection_protocols", "case_assignments")
        with sqlite3.connect(self.path) as db:
            return {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                    for table in tables}

    def test_wording_upgrade_preserves_observations_reviews_assignments_and_pinned_families(self):
        original = self.original_catalog["versions"][0]
        review, _ = self.store.catalog.add_review({
            "request_id": str(uuid4()), "version_id": original["version_id"],
            "reviewer_code": "TEST_REVIEWER", "reviewed_on": datetime.now(timezone.utc).date().isoformat(),
            "comments": "Software test only.", "disposition": "approved", "supersedes_review_id": None,
        })
        protocol, _ = self.store.collection.save_protocol({
            "request_id": str(uuid4()), "based_on_protocol_id": None,
            "title": "Synthetic migration test", "owner_code": "", "physician_codes": ["DEMO_01"],
            "consent_statement": "", "consent_version": "", "retention_days": None,
            "backup_owner_code": "", "backup_frequency": "manual_before_changes",
            "backup_retention_days": None, "notes": "Temporary software test only.",
        })
        assignment, _ = self.store.collection.assign({
            "request_id": str(uuid4()), "protocol_id": protocol["protocol_id"],
            "physician_code": "DEMO_01", "version_id": original["version_id"], "notes": "",
        })
        presentation = self.store.present(assignment_id=assignment["assignment_id"], capture_mode="fabricated_qa", qa_acknowledged=True)
        response, _ = self.store.submit(presentation["presentation_id"], values())
        before = self.payload_rows()
        upgraded = Store(self.path)
        after = self.payload_rows()
        for table, rows in before.items():
            with self.subTest(table=table):
                self.assertEqual(after[table][:len(rows)], rows)
                if table != "case_versions":
                    self.assertEqual(after[table], rows)
        catalog = upgraded.catalog.overview()
        self.assertEqual(len(catalog["versions"]), 20)
        self.assertEqual(catalog["reviews"], [review])
        self.assertEqual(catalog["families"], self.original_catalog["families"])
        self.assertEqual(upgraded.collection.overview()["assignments"], [assignment])
        self.assertEqual(upgraded.responses(), [response])
        self.assertEqual(Store(self.path).catalog.overview(), catalog)
        self.assertEqual(self.payload_rows(), after)

        latest = upgraded.present(case_id=original["case_id"], capture_mode="fabricated_qa", qa_acknowledged=True)
        self.assertEqual(latest["case_snapshot"]["version"], "1.1")
        self.assertEqual(latest["case_snapshot"]["review_status"], "unreviewed")
        self.assertIsNone(latest["case_review_id"])
        pinned = upgraded.present(assignment_id=assignment["assignment_id"], capture_mode="fabricated_qa", qa_acknowledged=True)
        self.assertEqual(pinned["case_snapshot"], presentation["case_snapshot"])
        self.assertEqual(pinned["case_review_id"], review["review_id"])
        correction = upgraded.present(supersedes_response_id=response["response_id"], capture_mode="fabricated_qa", qa_acknowledged=True)
        corrected, _ = upgraded.submit(correction["presentation_id"], values(next_action="Correction"))
        for field in ("case_snapshot", "case_version_id", "case_review_id", "assignment_id", "protocol_id"):
            self.assertEqual(corrected[field], response[field])

    def test_latest_cases_only_change_requested_wording_and_retain_matched_facts(self):
        upgraded = Store(self.path)
        catalog = upgraded.catalog.overview()
        for original in self.original_catalog["versions"]:
            with self.subTest(case_id=original["case_id"]):
                latest = latest_version(catalog, original["case_id"])
                expected = copy.deepcopy(original["snapshot"])
                expected["version"] = "1.1"
                expected["narrative"] = expected["narrative"].replace("fictional ", "")
                for fact in expected["decision_time_facts"]:
                    fact["value"] = fact["value"].replace("fictional ", "")
                self.assertEqual(latest["snapshot"], expected)
                self.assertEqual(latest["based_on_version"], original["version_id"])
                self.assertEqual(latest["snapshot_sha256"], snapshot_hash(expected))
                self.assertEqual(latest["snapshot"]["provenance"], original["snapshot"]["provenance"])
                self.assertNotIn("fictional", latest["snapshot"]["narrative"])
                for fact in latest["snapshot"]["decision_time_facts"]:
                    self.assertNotIn("fictional", fact["value"])
        originals = {v["version_id"]: v for v in self.original_catalog["versions"]}
        for family in catalog["families"]:
            base_id = originals[family["base_version_id"]]["case_id"]
            variant_id = originals[family["variant_version_id"]]["case_id"]
            base = latest_version(catalog, base_id)["snapshot"]
            variant = latest_version(catalog, variant_id)["snapshot"]
            self.assertEqual(base["narrative"], variant["narrative"])
            changed = [(left, right) for left, right in
                       zip(base["decision_time_facts"], variant["decision_time_facts"])
                       if left != right]
            self.assertEqual(len(changed), 1)
            self.assertEqual(changed[0][0]["label"], family["changed_fact"]["label"])
            self.assertEqual(changed[0][1]["label"], family["changed_fact"]["label"])

    def test_existing_local_revision_is_never_replaced_by_source_wording_upgrade(self):
        original = self.original_catalog["versions"][0]
        snapshot = copy.deepcopy(original["snapshot"])
        snapshot.update(version="1.1", narrative="Locally authored fictional scenario, retained verbatim.")
        local, _ = self.store.catalog.add_version({
            "request_id": str(uuid4()), "based_on_version_id": original["version_id"],
            "version": snapshot["version"], "editor_code": "TEST_EDITOR",
            "change_note": "Pre-existing local test revision.", "snapshot": snapshot,
        })
        upgraded = Store(self.path)
        self.assertEqual(latest_version(upgraded.catalog.overview(), original["case_id"]), local)
        self.assertEqual(upgraded.cases()[0], snapshot)
        self.assertEqual(len(upgraded.catalog.overview()["versions"]), 20)
        self.assertEqual(Store(self.path).catalog.overview(), upgraded.catalog.overview())


if __name__ == "__main__":
    unittest.main()

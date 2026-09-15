"""Temporary-database acceptance checks for immutable local review history."""

import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from helpers import latest_version, values

from twin_lab.schemas import ValidationError, snapshot_hash
from twin_lab.store import Conflict, NotFound, Store


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "catalog.sqlite3"
        self.store = Store(self.path)
        self.version = latest_version(self.store.catalog.overview())

    def review_body(self, **changes):
        body = {
            "request_id": str(uuid4()),
            "version_id": self.version["version_id"],
            "reviewer_code": "TEST_REVIEWER",
            "reviewed_on": date.today().isoformat(),
            "comments": "Synthetic software test only; no clinical approval.",
            "disposition": "approved",
            "supersedes_review_id": None,
        }
        body.update(changes)
        return body

    def revision_body(self, **changes):
        snapshot = copy.deepcopy(self.version["snapshot"])
        snapshot["version"] = "test-revision-2"
        snapshot["narrative"] += " Synthetic wording revision for a software test."
        body = {
            "request_id": str(uuid4()),
            "based_on_version_id": self.version["version_id"],
            "version": snapshot["version"],
            "editor_code": "TEST_EDITOR",
            "change_note": "Software test wording change.",
            "snapshot": snapshot,
        }
        body.update(changes)
        return body

    def test_ten_cases_and_five_pairs_are_synthetic_and_ineligible(self):
        catalog = self.store.catalog.overview()
        self.assertEqual(len(self.store.cases()), 10)
        self.assertEqual(len(catalog["families"]), 5)
        self.assertEqual(len(catalog["versions"]), 20)
        for version in catalog["versions"]:
            snapshot = version["snapshot"]
            self.assertIs(snapshot["synthetic"], True)
            self.assertIs(snapshot["eligible_for_study"], False)
            self.assertEqual(snapshot["review_status"], "unreviewed")
            self.assertEqual(snapshot["collection_purpose"], "demo")
            self.assertIsNone(version["latest_review"])
            self.assertEqual(version["snapshot_sha256"], snapshot_hash(snapshot))

    def test_each_matched_pair_changes_exactly_one_declared_fact(self):
        catalog = self.store.catalog.overview()
        versions = {v["version_id"]: v for v in catalog["versions"]}
        for family in catalog["families"]:
            with self.subTest(family=family["family_id"]):
                base = versions[family["base_version_id"]]["snapshot"]
                variant = versions[family["variant_version_id"]]["snapshot"]
                self.assertNotEqual(base["case_id"], variant["case_id"])
                self.assertEqual(base["family_id"], variant["family_id"])
                self.assertEqual(base["care_setting"], variant["care_setting"])
                self.assertEqual(base["narrative"], variant["narrative"])
                self.assertEqual(
                    len(base["decision_time_facts"]), len(variant["decision_time_facts"])
                )
                changed = [
                    (left, right)
                    for left, right in zip(
                        base["decision_time_facts"], variant["decision_time_facts"]
                    )
                    if left != right
                ]
                self.assertEqual(len(changed), 1)
                self.assertEqual(changed[0][0]["label"], changed[0][1]["label"])
                self.assertTrue(family["held_constant"])
                declaration = str(family["changed_fact"])
                self.assertIn(changed[0][0]["label"], declaration)
                self.assertIn(changed[0][0]["value"], declaration)
                self.assertIn(changed[0][1]["value"], declaration)

    def test_review_survives_restart_and_identical_retry(self):
        body = self.review_body()
        record, duplicate = self.store.catalog.add_review(body)
        self.assertFalse(duplicate)
        restarted = Store(self.path)
        retried, duplicate = restarted.catalog.add_review(body)
        self.assertTrue(duplicate)
        self.assertEqual(record, retried)
        self.assertEqual(restarted.catalog.overview()["reviews"], [record])
        changed = dict(body, comments="A changed retry must not overwrite.")
        with self.assertRaises(Conflict):
            restarted.catalog.add_review(changed)
        self.assertEqual(restarted.catalog.overview()["reviews"], [record])

    def test_stale_and_concurrent_reviews_cannot_fork_history(self):
        first, _ = self.store.catalog.add_review(self.review_body())
        with self.assertRaises(Conflict):
            self.store.catalog.add_review(self.review_body(disposition="rejected"))
        left = self.review_body(
            supersedes_review_id=first["review_id"], disposition="needs_revision"
        )
        right = self.review_body(supersedes_review_id=first["review_id"], disposition="rejected")

        def attempt(body):
            try:
                return self.store.catalog.add_review(body)[0]
            except Conflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, (left, right)))
        self.assertEqual(sum(result is not None for result in results), 1)
        reviews = self.store.catalog.overview()["reviews"]
        self.assertEqual(len(reviews), 2)
        self.assertEqual(reviews[0], first)
        self.assertEqual(reviews[1]["supersedes_review_id"], first["review_id"])

    def test_review_rejects_unknown_fields_dates_and_missing_versions(self):
        invalid = (
            {"study_collection_enabled": True},
            {"reviewer_code": "name@example.test"},
            {"reviewed_on": (date.today() + timedelta(days=2)).isoformat()},
            {"reviewed_on": "2026-02-30"},
            {"disposition": "study_ready"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.store.catalog.add_review(self.review_body(**changes))
        with self.assertRaises(NotFound):
            self.store.catalog.add_review(self.review_body(version_id=str(uuid4())))
        self.assertEqual(self.store.catalog.overview()["reviews"], [])

    def test_revision_preserves_prior_case_and_resets_review(self):
        original = copy.deepcopy(self.version)
        self.store.catalog.add_review(self.review_body())
        body = self.revision_body()
        created, duplicate = self.store.catalog.add_version(body)
        self.assertFalse(duplicate)
        self.assertEqual(created["based_on_version"], original["version_id"])
        self.assertEqual(created["snapshot"], body["snapshot"])
        self.assertIsNone(created["latest_review"])
        self.assertEqual(created["snapshot"]["review_status"], "unreviewed")
        self.assertIs(created["snapshot"]["eligible_for_study"], False)
        restarted = Store(self.path)
        versions = restarted.catalog.overview()["versions"]
        old = next(v for v in versions if v["version_id"] == original["version_id"])
        self.assertEqual(old["snapshot"], original["snapshot"])
        retried, duplicate = restarted.catalog.add_version(body)
        self.assertTrue(duplicate)
        self.assertEqual(retried, created)
        with self.assertRaises(Conflict):
            restarted.catalog.add_version(dict(body, change_note="Changed retry"))
        with self.assertRaises(Conflict):
            restarted.catalog.add_version(self.revision_body())

    def test_revision_cannot_change_case_identity_family_or_add_hidden_facts(self):
        for field, value in (
            ("case_id", str(uuid4())),
            ("family_id", str(uuid4())),
            ("answer_key", "Not allowed"),
        ):
            body = self.revision_body()
            body["snapshot"][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.store.catalog.add_version(body)
        self.assertEqual(len(self.store.catalog.overview()["versions"]), 20)

    def test_response_pins_review_and_version_at_presentation_and_correction(self):
        approved, _ = self.store.catalog.add_review(self.review_body())
        presentation = self.store.present(
            version_id=self.version["version_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        self.store.catalog.add_review(
            self.review_body(
                disposition="needs_revision", supersedes_review_id=approved["review_id"]
            )
        )
        self.store.catalog.add_version(self.revision_body())
        response, _ = self.store.submit(presentation["presentation_id"], values())
        self.assertEqual(response["case_version_id"], self.version["version_id"])
        self.assertEqual(response["case_review_id"], approved["review_id"])
        self.assertEqual(response["case_review_status"], "approved")
        self.assertEqual(response["case_snapshot"], presentation["case_snapshot"])
        self.assertEqual(response["case_version"], self.version["case_version"])
        self.assertIs(response["eligible_for_study"], False)
        correction = self.store.present(
            supersedes_response_id=response["response_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        corrected, _ = self.store.submit(
            correction["presentation_id"], values(next_action="Correction")
        )
        for field in ("case_version_id", "case_review_id", "case_snapshot", "snapshot_sha256"):
            self.assertEqual(corrected[field], response[field])
        self.assertEqual(self.store.responses(), [response, corrected])


if __name__ == "__main__":
    unittest.main()

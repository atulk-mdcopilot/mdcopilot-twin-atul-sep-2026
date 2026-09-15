import copy
import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from helpers import FIXTURES, values

from twin_lab.schemas import ValidationError
from twin_lab.store import Conflict, NotFound, Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "observations.sqlite3"
        self.fixture_path = Path(self.temp.name) / "cases.json"
        self.fixture_path.write_bytes(FIXTURES.read_bytes())
        self.store = Store(self.db, self.fixture_path)
        self.case = self.store.cases()[0]

    def present(self):
        return self.store.present(
            case_id=self.case["case_id"], capture_mode="fabricated_qa", qa_acknowledged=True
        )

    def save(self, submitted=None):
        presentation = self.present()
        response, duplicate = self.store.submit(
            presentation["presentation_id"], submitted or values()
        )
        self.assertFalse(duplicate)
        return response

    def test_save_retains_version_snapshot_originals_and_metadata(self):
        submitted = values(rationale="  Optional short explanation.\n", confidence="moderate")
        original = copy.deepcopy(submitted)
        presentation = self.present()
        response, duplicate = self.store.submit(presentation["presentation_id"], submitted)
        self.assertFalse(duplicate)
        self.assertEqual(submitted, original)
        self.assertEqual(response["original_values"], original)
        normalized = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in original.items()
        }
        self.assertEqual(response["normalized_values"], normalized)
        self.assertEqual(response["physician_code"], "DEMO_01")
        self.assertEqual(response["case_id"], self.case["case_id"])
        self.assertEqual(response["case_family"], self.case["family_id"])
        self.assertEqual(response["case_version"], self.case["version"])
        self.assertEqual(response["response_schema_version"], "1.2")
        self.assertEqual(response["case_snapshot"], self.case)
        self.assertEqual(response["presented_at"], presentation["presented_at"])
        digest = hashlib.sha256(
            json.dumps(self.case, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
        self.assertEqual(response["snapshot_sha256"], digest)
        self.assertEqual(presentation["snapshot_sha256"], digest)
        self.assertIs(response["ai_advice_shown"], False)
        self.assertIs(response["eligible_for_study"], False)
        self.assertEqual(response["case_review_status"], "unreviewed")
        self.assertEqual(response["collection_purpose"], "demo")
        self.assertIsNone(response["supersedes_response_id"])
        UUID(response["response_id"])
        UUID(response["presentation_id"])
        times = [
            datetime.fromisoformat(response[key].replace("Z", "+00:00"))
            for key in ("presented_at", "submitted_at")
        ]
        self.assertTrue(
            all(timestamp.utcoffset() == timezone.utc.utcoffset(timestamp) for timestamp in times)
        )
        self.assertLessEqual(times[0], times[1])

    def test_restart_and_fixture_changes_preserve_original_presentation(self):
        presentation = self.present()
        cases = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        cases[0]["version"] = "changed-version"
        cases[0]["narrative"] = "A revised synthetic fixture narrative."
        self.fixture_path.write_text(json.dumps(cases), encoding="utf-8")
        restarted = Store(self.db, self.fixture_path)
        response, duplicate = restarted.submit(presentation["presentation_id"], values())
        self.assertFalse(duplicate)
        self.assertEqual(response["case_snapshot"], self.case)
        self.assertEqual(response["case_version"], self.case["version"])
        self.assertEqual(Store(self.db, self.fixture_path).responses(), [response])
        correction = restarted.present(
            supersedes_response_id=response["response_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        self.assertEqual(correction["case_snapshot"], self.case)

    def test_invalid_submission_leaves_no_saved_observation(self):
        presentation = self.present()
        with self.assertRaises(ValidationError):
            self.store.submit(presentation["presentation_id"], values(next_action=" "))
        self.assertEqual(self.store.responses(), [])
        with self.assertRaises(NotFound):
            self.store.submit("00000000-0000-0000-0000-000000000000", values())
        self.assertEqual(self.store.responses(), [])

    def test_identical_retries_survive_restart_but_changed_retries_conflict(self):
        presentation = self.present()
        first, duplicate = self.store.submit(presentation["presentation_id"], values())
        self.assertFalse(duplicate)
        restarted = Store(self.db, self.fixture_path)
        retry, duplicate = restarted.submit(presentation["presentation_id"], values())
        self.assertTrue(duplicate)
        self.assertEqual(retry, first)
        with self.assertRaises(Conflict):
            restarted.submit(presentation["presentation_id"], values(next_action="Changed"))
        self.assertEqual(restarted.responses(), [first])

    def test_concurrent_duplicate_saves_create_one_observation(self):
        presentation = self.present()
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(
                executor.map(
                    lambda _: self.store.submit(presentation["presentation_id"], values()),
                    range(6),
                )
            )
        self.assertEqual(len({response["response_id"] for response, _ in results}), 1)
        self.assertEqual(sum(not duplicate for _, duplicate in results), 1)
        self.assertEqual(len(self.store.responses()), 1)

    def test_explicit_correction_preserves_original_and_requires_same_code(self):
        first = self.save()
        presentation = self.store.present(
            supersedes_response_id=first["response_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        with self.assertRaises(Conflict):
            self.store.submit(presentation["presentation_id"], values(physician_code="OTHER"))
        self.assertEqual(self.store.responses(), [first])
        corrected, duplicate = self.store.submit(
            presentation["presentation_id"],
            values(physician_code="DEMO_01", next_action="An explicit corrected action."),
        )
        self.assertFalse(duplicate)
        self.assertEqual(corrected["supersedes_response_id"], first["response_id"])
        self.assertNotEqual(corrected["response_id"], first["response_id"])
        self.assertEqual(self.store.responses(), [first, corrected])
        with self.assertRaises(Conflict):
            self.store.present(
                supersedes_response_id=first["response_id"],
                capture_mode="fabricated_qa",
                qa_acknowledged=True,
            )
        latest = self.store.present(
            supersedes_response_id=corrected["response_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        self.assertEqual(latest["supersedes_response_id"], corrected["response_id"])

    def test_two_pending_corrections_cannot_create_forked_history(self):
        first = self.save()
        left = self.store.present(
            supersedes_response_id=first["response_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        right = self.store.present(
            supersedes_response_id=first["response_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        second, _ = self.store.submit(left["presentation_id"], values(next_action="Correction A"))
        with self.assertRaises(Conflict):
            self.store.submit(right["presentation_id"], values(next_action="Correction B"))
        self.assertEqual(self.store.responses(), [first, second])

    def test_export_envelope_contains_every_saved_original_and_revision(self):
        first = self.save(values(next_action="<script>local text only</script>"))
        presentation = self.store.present(
            supersedes_response_id=first["response_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        second, _ = self.store.submit(
            presentation["presentation_id"], values(next_action="Correction")
        )
        exported = self.store.export()
        self.assertEqual(
            set(exported),
            {
                "export_schema_version",
                "exported_at",
                "application",
                "synthetic_only",
                "response_count",
                "responses",
                "case_versions",
                "case_reviews",
                "case_families",
                "collection_protocols",
                "assignments",
            },
        )
        self.assertEqual(exported["export_schema_version"], "1.2")
        self.assertEqual(exported["application"], "Twin Lab v0.1")
        self.assertIs(exported["synthetic_only"], True)
        self.assertEqual(exported["response_count"], 2)
        self.assertEqual(exported["responses"], [first, second])
        self.assertEqual(json.loads(json.dumps(exported))["responses"], [first, second])


if __name__ == "__main__":
    unittest.main()

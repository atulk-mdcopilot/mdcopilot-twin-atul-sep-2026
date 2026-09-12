import copy
import json
import unittest

from helpers import FIXTURES, values
from twin_lab.schemas import ValidationError, validate_case, validate_values


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads(FIXTURES.read_text(encoding="utf-8"))

    def test_five_distinct_explicitly_synthetic_unreviewed_demo_cases(self):
        self.assertEqual(len(self.cases), 5)
        self.assertEqual(len({case["case_id"] for case in self.cases}), 5)
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                original = copy.deepcopy(case)
                self.assertEqual(validate_case(case), original)
                self.assertEqual(case, original)
                self.assertIs(case["synthetic"], True)
                self.assertEqual(case["review_status"], "unreviewed")
                self.assertIs(case["eligible_for_study"], False)
                self.assertEqual(case["collection_purpose"], "demo")
                self.assertTrue(case["provenance"].strip())
                self.assertTrue(case["decision_time_facts"])

    def test_hidden_labels_and_outcomes_are_rejected(self):
        for key in ("hidden_diagnosis", "answer_key", "future_outcome", "outcome"):
            with self.subTest(key=key):
                case = copy.deepcopy(self.cases[0])
                case[key] = "Never display this"
                with self.assertRaises(ValidationError):
                    validate_case(case)
        case = copy.deepcopy(self.cases[0])
        case["decision_time_facts"][0]["hidden_label"] = "not allowed"
        with self.assertRaises(ValidationError):
            validate_case(case)

    def test_fixture_boundary_rejects_non_demo_or_malformed_content(self):
        invalid = {
            "synthetic": False,
            "eligible_for_study": True,
            "review_status": "reviewed",
            "collection_purpose": "clinical",
            "version": " ",
            "narrative": "",
            "decision_time_facts": [],
        }
        for key, value in invalid.items():
            with self.subTest(key=key):
                case = copy.deepcopy(self.cases[0])
                case[key] = value
                with self.assertRaises(ValidationError):
                    validate_case(case)

    def test_values_preserve_original_text_and_allow_optional_answers(self):
        submitted = values()
        original = copy.deepcopy(submitted)
        self.assertEqual(validate_values(submitted), original)
        self.assertEqual(submitted, original)
        for confidence in (None, "low", "moderate", "high"):
            self.assertEqual(
                validate_values(values(confidence=confidence))["confidence"],
                confidence,
            )

    def test_missing_empty_malformed_required_values_cannot_be_saved(self):
        for field in ("physician_code", "next_action", "next_information", "decision_change"):
            for invalid in (None, "", " \n ", 42, True, [], {}):
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaises(ValidationError):
                        validate_values(values(**{field: invalid}))
        for field in values():
            with self.subTest(missing=field):
                submitted = values()
                del submitted[field]
                with self.assertRaises(ValidationError):
                    validate_values(submitted)
        with self.assertRaises(ValidationError):
            validate_values(values(extra="not in the contract"))

    def test_code_text_and_confidence_limits(self):
        for code in ("a" * 41, "has space", "a\nb", "name@example.test", "../local"):
            with self.subTest(code=code):
                with self.assertRaises(ValidationError):
                    validate_values(values(physician_code=code))
        for confidence in (0.5, 100, True, "certain", "", [], {}):
            with self.subTest(confidence=confidence):
                with self.assertRaises(ValidationError):
                    validate_values(values(confidence=confidence))
        for field in ("next_action", "next_information", "decision_change", "rationale"):
            with self.subTest(long_field=field):
                with self.assertRaises(ValidationError):
                    validate_values(values(**{field: "x" * 5001}))


if __name__ == "__main__":
    unittest.main()

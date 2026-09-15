"""Versioned pilot contracts use fabricated governance and independently checked UTC dates."""

import copy
import json
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import test_governance as governance_tests
from helpers import linked_plan_body, values

from twin_lab.governance_schema import validate_governance
from twin_lab.schemas import Conflict, ValidationError
from twin_lab.store import Store


def pilot_body(legacy, *, start=None, close=None, anniversary=None):
    """Test-only explicit conversion, with no implicit February-29 choice."""
    body = copy.deepcopy(legacy)
    body["governance_schema_version"] = "2.0"
    body["operator"]["professional_role"] = "Fabricated reviewing role"
    body["operator"]["pilot_start_date"] = start or datetime.now(timezone.utc).date().isoformat()
    if close:
        body["operator"]["pilot_close_date"] = close
    end = date.fromisoformat(body["operator"]["pilot_close_date"])
    anniversary = date.fromisoformat(anniversary) if anniversary else end.replace(year=end.year + 1)
    body["session"] = {
        "description": "Fabricated session scope. Café.\n",
        "max_distinct_case_versions": 2,
    }
    body["retention"].update(
        calendar_year_basis={
            "pilot_close_date": end.isoformat(),
            "anniversary_date": anniversary.isoformat(),
        },
        permission_after_close_days=(anniversary - end).days,
        audit_after_close_days=(anniversary - end).days,
    )
    return body


class PilotContractTests(unittest.TestCase):
    setUp = governance_tests.GovernanceTests.setUp
    draft = staticmethod(governance_tests.GovernanceTests.draft)
    approved_body = governance_tests.GovernanceTests.approved_body
    record_review = governance_tests.GovernanceTests.record_review
    permission_body = governance_tests.GovernanceTests.permission_body

    def create_plan(self):
        current = self.governance.overview()["current"]
        if current["governance_schema_version"] == "1.0":
            return governance_tests.GovernanceTests.create_plan(self)
        plan, _ = self.store.collection.save_protocol(linked_plan_body(current["governance_id"]))
        assigned, _ = self.store.collection.assign(
            {
                "request_id": str(uuid4()),
                "protocol_id": plan["protocol_id"],
                "physician_code": "PHY-QA",
                "version_id": self.version["version_id"],
                "notes": "Fabricated assigned version.",
            }
        )
        return plan, assigned

    def test_new_draft_preserves_unknown_fields_without_inventing_approval(self):
        body = self.draft()
        body["governance_schema_version"] = "2.0"
        body["operator"].update(professional_role="", pilot_start_date="")
        body["session"] = {"description": "", "max_distinct_case_versions": None}
        body["retention"]["calendar_year_basis"] = None
        saved, duplicate = self.governance.save(body)
        self.assertFalse(duplicate)
        self.assertEqual(saved["operator"], body["operator"])
        self.assertEqual(saved["session"], body["session"])
        self.assertIsNone(saved["retention"]["calendar_year_basis"])
        missing = self.governance.overview()["readiness"]["missing_fields"]
        for field in (
            "operator.professional_role",
            "operator.pilot_start_date",
            "session.description",
            "session.max_distinct_case_versions",
            "retention.calendar_year_basis",
        ):
            self.assertIn(field, missing)
        self.assertFalse(
            self.governance.overview()["readiness"]["actual_physician_capture_enabled"]
        )
        self.assertEqual(self.governance.overview()["receipts"], [])

    def test_strict_v2_fields_dates_and_limits(self):
        good = pilot_body(self.approved_body())
        self.assertEqual(validate_governance(good), good)
        for limit in (1, 200):
            bounded = copy.deepcopy(good)
            bounded["session"]["max_distinct_case_versions"] = limit
            self.assertEqual(validate_governance(bounded), bounded)
        invalid = []
        for section in ("operator", "session", "retention"):
            for value in (None, {}, []):
                malformed = copy.deepcopy(good)
                malformed[section] = value
                invalid.append(malformed)
        for value in (0, -1, 201, True, "2", 1.5):
            changed = copy.deepcopy(good)
            changed["session"]["max_distinct_case_versions"] = value
            invalid.append(changed)
        for section, key in (("session", "total_responses"), ("operator", "timezone")):
            changed = copy.deepcopy(good)
            changed[section][key] = "unexpected"
            invalid.append(changed)
        changed = copy.deepcopy(good)
        changed["operator"]["pilot_start_date"] = "2099-12-31"
        invalid.append(changed)
        changed = copy.deepcopy(good)
        changed["operator"]["pilot_start_date"] = "2026-9-01"
        invalid.append(changed)
        for marker in ("1.0", "3.0", None):
            invalid.append(dict(good, governance_schema_version=marker))
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(ValidationError):
                self.governance.save(body)
        self.assertEqual(self.governance.overview()["history"], [])

    def test_future_pilot_can_be_approved_but_capture_uses_exact_utc_window(self):
        body = pilot_body(self.approved_body(), start="2050-09-11", close="2050-09-15")
        governance, _ = self.governance.save(body)
        self.create_plan()
        self.record_review()
        for instant, allowed in (
            ("2050-09-10T23:59:59.999999+00:00", False),
            ("2050-09-11T00:00:00+00:00", True),
            ("2050-09-15T23:59:59.999999+00:00", True),
            ("2050-09-16T00:00:00+00:00", False),
        ):
            with (
                self.subTest(instant=instant),
                patch("twin_lab.governance_schema.datetime", wraps=datetime) as clock,
            ):
                clock.now.return_value = datetime.fromisoformat(instant)
                readiness = self.governance.overview()["readiness"]
                self.assertIs(readiness["actual_physician_capture_enabled"], allowed)
                if allowed:
                    receipt, _ = self.governance.permission(self.permission_body(governance))
                    self.assertEqual(receipt["choice"], "agree")
                else:
                    with self.assertRaises(Conflict):
                        self.governance.permission(self.permission_body(governance))

    def test_crossing_close_after_presentation_blocks_submit_and_retry(self):
        body = pilot_body(self.approved_body(), start="2050-09-11", close="2050-09-15")
        governance, _ = self.governance.save(body)
        _, assignment = self.create_plan()
        self.record_review()
        with patch("twin_lab.governance_schema.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2050, 9, 15, 23, 59, 59, tzinfo=timezone.utc)
            permission_request = self.permission_body(governance)
            receipt, _ = self.governance.permission(permission_request)
            selector = {
                "assignment_id": assignment["assignment_id"],
                "capture_mode": "physician_demo",
                "permission_receipt_id": receipt["receipt_id"],
            }
            saved_presentation = self.store.present(**selector)
            saved, _ = self.store.submit(
                saved_presentation["presentation_id"], values(physician_code="PHY-QA")
            )
            pending = self.store.present(**selector)
            clock.now.return_value = datetime(2050, 9, 16, tzinfo=timezone.utc)
            with self.assertRaises(Conflict):
                self.governance.permission(permission_request)
            for presentation_id in (
                saved_presentation["presentation_id"],
                pending["presentation_id"],
            ):
                with self.assertRaises(Conflict):
                    self.store.submit(presentation_id, values(physician_code="PHY-QA"))
            with self.assertRaises(Conflict):
                self.store.present(**selector)
        self.assertEqual(self.store.responses(), [saved])

    def test_calendar_years_require_recorded_basis_and_match_administrative_periods(self):
        for close, anniversary, expected in (
            ("2027-03-01", "2028-03-01", 366),
            ("2028-03-01", "2029-03-01", 365),
            ("2028-02-29", "2029-02-28", 365),
            ("2028-02-29", "2029-03-01", 366),
        ):
            with self.subTest(close=close, anniversary=anniversary):
                body = pilot_body(
                    self.approved_body(), start=close, close=close, anniversary=anniversary
                )
                self.assertEqual(body["retention"]["permission_after_close_days"], expected)
                current = self.governance.overview()["current"]
                body["based_on_governance_id"] = current["governance_id"] if current else None
                body["permission"]["version"] = str(uuid4())
                saved, _ = self.governance.save(body)
                self.assertEqual(
                    saved["retention"]["calendar_year_basis"],
                    body["retention"]["calendar_year_basis"],
                )
        incomplete = pilot_body(self.approved_body())
        incomplete["based_on_governance_id"] = saved["governance_id"]
        incomplete["retention"]["calendar_year_basis"] = None
        with self.assertRaises(ValidationError):
            self.governance.save(incomplete)
        incomplete["status"] = "draft"
        self.governance.save(incomplete)
        self.assertIn(
            "retention.calendar_year_basis",
            self.governance.overview()["readiness"]["missing_fields"],
        )

    def test_stale_close_conversion_and_wrong_day_count_cannot_be_approved(self):
        body = pilot_body(self.approved_body(), start="2027-03-01", close="2027-03-01")
        body["operator"]["pilot_close_date"] = "2028-03-01"
        with self.assertRaises(ValidationError):
            self.governance.save(body)
        body = pilot_body(self.approved_body(), start="2027-03-01", close="2027-03-01")
        body["retention"]["audit_after_close_days"] = 365
        with self.assertRaises(ValidationError):
            self.governance.save(body)
        body["status"] = "draft"
        self.governance.save(body)
        self.assertIn(
            "retention.audit_after_close_days_calendar_year",
            self.governance.overview()["readiness"]["missing_fields"],
        )

    def test_scope_change_requires_new_notice_version_even_with_unchanged_text(self):
        first_body = pilot_body(self.approved_body())
        first, _ = self.governance.save(first_body)
        for section, key, value in (
            ("session", "description", "Changed scope."),
            ("session", "max_distinct_case_versions", 3),
            ("operator", "professional_role", "Changed role"),
            ("operator", "pilot_start_date", "2026-01-01"),
        ):
            changed = copy.deepcopy(first_body)
            changed.update(request_id=str(uuid4()), based_on_governance_id=first["governance_id"])
            changed[section][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(Conflict, "version"):
                self.governance.save(changed)
        changed["permission"]["version"] = "TEST-PERM-2"
        latest, _ = self.governance.save(changed)
        self.assertEqual(latest["permission"]["text"], first["permission"]["text"])

    def test_v1_history_retry_and_gate_remain_until_explicit_v2_without_downgrade(self):
        old_body = self.approved_body()
        original, _ = self.governance.save(old_body)
        _, assignment = self.create_plan()
        self.record_review()
        old_receipt, _ = self.governance.permission(self.permission_body(original))
        before = self.store.present(
            assignment_id=assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=old_receipt["receipt_id"],
        )
        response, _ = self.store.submit(before["presentation_id"], values(physician_code="PHY-QA"))
        with self.store.connection() as db:
            tables = (
                "governance_versions",
                "permission_receipts",
                "presentations",
                "responses",
                "response_lifecycle",
            )
            rows = {
                table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                for table in tables
            }
            db.execute("PRAGMA user_version = 3")
        upgraded = Store(self.path)
        self.assertEqual(upgraded.governance.overview()["current"], original)
        self.assertNotIn("session", original)
        self.assertNotIn("professional_role", original["operator"])
        changed = pilot_body(self.approved_body())
        changed["based_on_governance_id"] = original["governance_id"]
        changed["permission"]["version"] = "TEST-PERM-V2"
        current, _ = upgraded.governance.save(changed)
        self.assertEqual(upgraded.governance.save(old_body), (original, True))
        downgrade = dict(
            old_body, request_id=str(uuid4()), based_on_governance_id=current["governance_id"]
        )
        with self.assertRaisesRegex(Conflict, "v2|version 2"):
            upgraded.governance.save(downgrade)
        with self.assertRaises(Conflict):
            upgraded.submit(response["presentation_id"], response["original_values"])
        with upgraded.connection() as db:
            for table, previous in rows.items():
                self.assertEqual(
                    db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()[: len(previous)],
                    previous,
                )
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 4)
        self.assertEqual(Store(self.path).governance.overview()["current"], current)

    def test_intervening_draft_cannot_hide_changed_scope_under_an_approved_notice_version(self):
        first_body = pilot_body(self.approved_body())
        original, _ = self.governance.save(first_body)
        revised = copy.deepcopy(first_body)
        revised.update(
            request_id=str(uuid4()),
            based_on_governance_id=original["governance_id"],
            status="draft",
        )
        revised["session"]["description"] = "A different participant-facing scope."
        draft, _ = self.governance.save(revised)
        revised.update(
            request_id=str(uuid4()),
            based_on_governance_id=draft["governance_id"],
            status="approved",
        )
        with self.assertRaisesRegex(Conflict, "version"):
            self.governance.save(revised)
        self.assertEqual(self.governance.overview()["current"], draft)

    def test_permission_copies_shown_scope_privately_and_exports_keep_existing_schema(self):
        body = pilot_body(self.approved_body())
        governance, _ = self.governance.save(body)
        _, assignment = self.create_plan()
        self.record_review()
        receipt, _ = self.governance.permission(self.permission_body(governance))
        self.assertEqual(receipt["permission_schema_version"], "2.0")
        self.assertEqual(receipt["session"], body["session"])
        self.assertEqual(receipt["professional_role"], body["operator"]["professional_role"])
        self.assertEqual(
            receipt["pilot_window"],
            {key: body["operator"][key] for key in ("pilot_start_date", "pilot_close_date")},
        )
        presentation = self.store.present(
            assignment_id=assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )
        response, _ = self.store.submit(
            presentation["presentation_id"], values(physician_code="PHY-QA")
        )
        exported = self.store.export()
        self.assertEqual(exported["export_schema_version"], "1.2")
        self.assertEqual(response["response_schema_version"], "1.2")
        self.assertEqual(exported["responses"], [response])
        for private in (
            body["session"]["description"],
            body["operator"]["professional_role"],
            body["permission"]["text"],
        ):
            self.assertNotIn(
                json.dumps(private, ensure_ascii=False), json.dumps(exported, ensure_ascii=False)
            )
        self.assertEqual(Store(self.path).governance.receipt(receipt["receipt_id"]), receipt)


if __name__ == "__main__":
    unittest.main()

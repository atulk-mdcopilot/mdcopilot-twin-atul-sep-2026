"""Strict plan cutover, pinned policy and distinct-version scope use fabricated data."""

import copy
import json
import unittest
from datetime import datetime, timezone
from uuid import uuid4

import test_governance as governance_tests
from helpers import linked_plan_body, values
from test_pilot_contracts import pilot_body

from twin_lab.schemas import Conflict, NotFound, ValidationError
from twin_lab.store import Store


class LinkedPlanTests(unittest.TestCase):
    setUp = governance_tests.GovernanceTests.setUp
    draft = staticmethod(governance_tests.GovernanceTests.draft)
    approved_body = governance_tests.GovernanceTests.approved_body
    create_plan = governance_tests.GovernanceTests.create_plan
    record_review = governance_tests.GovernanceTests.record_review
    permission_body = governance_tests.GovernanceTests.permission_body

    def policy(self, *, legacy=False, **changes):
        body = self.approved_body(**changes)
        if not legacy:
            body = pilot_body(body)
        return self.governance.save(body)[0], body

    def plan(self, governance, parent=None, **changes):
        body = linked_plan_body(governance["governance_id"], parent, **changes)
        return self.store.collection.save_protocol(body)[0], body

    def assignment(self, plan, version_id=None, code="PHY-QA"):
        body = {
            "request_id": str(uuid4()),
            "protocol_id": plan["protocol_id"],
            "physician_code": code,
            "version_id": version_id or self.version["version_id"],
            "notes": "Fabricated exact-version assignment.",
        }
        return self.store.collection.assign(body)[0], body

    def ready(self, limit=2):
        body = pilot_body(self.approved_body())
        body["session"]["max_distinct_case_versions"] = limit
        governance, _ = self.governance.save(body)
        plan, _ = self.plan(governance)
        assignment, _ = self.assignment(plan)
        self.record_review()
        permission = self.permission_body(governance)
        receipt, _ = self.governance.permission(permission)
        return governance, body, plan, assignment, receipt, permission

    def present(self, assignment, receipt):
        return self.store.present(
            assignment_id=assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )

    def test_v2_plan_has_one_policy_source_and_strict_fields(self):
        governance, _ = self.policy(status="draft")
        plan, body = self.plan(governance)
        self.assertEqual(plan["protocol_schema_version"], "2.0")
        self.assertEqual(plan["governance_id"], governance["governance_id"])
        for field in (
            "consent_statement",
            "consent_version",
            "retention_days",
            "backup_retention_days",
            "session",
            "operator",
        ):
            self.assertNotIn(field, plan)
            invalid = dict(
                body,
                request_id=str(uuid4()),
                based_on_protocol_id=plan["protocol_id"],
                **{field: "unexpected"},
            )
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.store.collection.save_protocol(invalid)
        self.assertEqual(self.store.collection.save_protocol(body), (plan, True))
        for missing in body:
            invalid = dict(body)
            invalid.pop(missing)
            with self.subTest(missing=missing), self.assertRaises(ValidationError):
                self.store.collection.save_protocol(invalid)
        with self.assertRaises(NotFound):
            self.store.collection.save_protocol(linked_plan_body(str(uuid4()), plan["protocol_id"]))
        self.assertEqual(self.store.collection.overview()["history"], [plan])

    def test_draft_pin_is_planning_only_and_unknown_limit_is_not_invented(self):
        body = pilot_body(self.approved_body(status="draft"))
        body["session"]["max_distinct_case_versions"] = None
        governance, _ = self.governance.save(body)
        plan, _ = self.plan(governance)
        self.assignment(plan)
        self.record_review()
        self.assertTrue(self.store.collection.overview()["readiness"]["governance_pin_current"])
        with self.assertRaises(Conflict):
            self.governance.permission(self.permission_body(governance))
        self.assertIsNone(
            self.governance.overview()["current"]["session"]["max_distinct_case_versions"]
        )

    def test_legacy_plan_retry_preserves_bytes_but_new_v1_cannot_remove_v2_pin(self):
        governance, _ = self.policy(legacy=True)
        legacy, _ = self.create_plan()
        with self.store.connection() as db:
            original_rows = db.execute(
                "SELECT * FROM collection_protocols ORDER BY rowid"
            ).fetchall()
            legacy_body = json.loads(original_rows[0][2])
        current, body = self.plan(governance, legacy["protocol_id"])
        self.assertEqual(self.store.collection.save_protocol(legacy_body), (legacy, True))
        downgrade = dict(
            legacy_body, request_id=str(uuid4()), based_on_protocol_id=current["protocol_id"]
        )
        with self.assertRaisesRegex(Conflict, "v2|version 2"):
            self.store.collection.save_protocol(downgrade)
        with self.assertRaises(Conflict):
            self.store.collection.save_protocol(dict(body, title="Changed request ID content"))
        restarted = Store(self.path)
        self.assertEqual(restarted.collection.overview()["current"], current)
        with restarted.connection() as db:
            self.assertEqual(
                db.execute("SELECT * FROM collection_protocols ORDER BY rowid").fetchall()[:1],
                original_rows,
            )

    def test_new_governance_cannot_use_unlinked_legacy_plan_to_bypass_session_scope(self):
        old_governance, _ = self.policy(legacy=True)
        legacy_plan, old_assignment = self.create_plan()
        self.record_review()
        old_receipt, _ = self.governance.permission(self.permission_body(old_governance))
        self.present(old_assignment, old_receipt)
        new_body = pilot_body(
            self.approved_body(based_on_governance_id=old_governance["governance_id"])
        )
        new_body["permission"]["version"] = "TEST-NEW-SCOPE"
        current, _ = self.governance.save(new_body)
        readiness = self.store.collection.overview()["readiness"]
        self.assertFalse(readiness["governance_pin_current"])
        self.assertIn("linked_plan", readiness["missing_fields"])
        with self.assertRaisesRegex(Conflict, "linked|v2"):
            self.governance.permission(self.permission_body(current))
        linked, _ = self.plan(current, legacy_plan["protocol_id"])
        assigned, _ = self.assignment(linked)
        receipt, _ = self.governance.permission(self.permission_body(current))
        self.present(assigned, receipt)

    def test_stale_pin_blocks_permission_retries_presentations_and_saves_without_rebinding(self):
        governance, body, plan, assigned, receipt, permission = self.ready()
        presented = self.present(assigned, receipt)
        saved, _ = self.store.submit(presented["presentation_id"], values(physician_code="PHY-QA"))
        pending = self.present(assigned, receipt)
        revised = copy.deepcopy(body)
        revised.update(request_id=str(uuid4()), based_on_governance_id=governance["governance_id"])
        revised["permission"]["version"] = "TEST-NEXT-SCOPE"
        next_governance, _ = self.governance.save(revised)
        readiness = self.store.collection.overview()["readiness"]
        self.assertFalse(readiness["governance_pin_current"])
        self.assertIn("stale_governance", readiness["missing_fields"])
        for request in (permission, self.permission_body(next_governance)):
            with self.assertRaises(Conflict):
                self.governance.permission(request)
        with self.assertRaises(Conflict):
            self.present(assigned, receipt)
        for presentation_id in (presented["presentation_id"], pending["presentation_id"]):
            with self.assertRaises(Conflict):
                self.store.submit(presentation_id, values(physician_code="PHY-QA"))
        self.assertEqual(self.governance.receipt(receipt["receipt_id"]), receipt)
        next_plan, _ = self.plan(next_governance, plan["protocol_id"])
        next_assignment, _ = self.assignment(next_plan)
        next_receipt, _ = self.governance.permission(self.permission_body(next_governance))
        self.present(next_assignment, next_receipt)
        with self.assertRaises(Conflict):
            self.store.present(
                supersedes_response_id=saved["response_id"],
                capture_mode="physician_demo",
                permission_receipt_id=receipt["receipt_id"],
            )
        self.assertEqual(self.store.responses(), [saved])
        self.assertEqual(self.store.collection.overview()["history"], [plan, next_plan])

    def test_distinct_version_cap_counts_union_across_plans_but_separately_per_code(self):
        governance, _ = self.policy()
        versions = [
            record["version_id"] for record in self.store.catalog.overview()["versions"][:3]
        ]
        first, _ = self.plan(governance)
        self.assignment(first, versions[0])
        second, _ = self.plan(governance, first["protocol_id"])
        repeated, repeat_body = self.assignment(second, versions[0])
        self.assertEqual(self.store.collection.assign(repeat_body), (repeated, True))
        self.assignment(second, versions[1])
        before = self.store.collection.overview()["assignments"]
        with self.assertRaisesRegex(Conflict, "distinct|limit"):
            self.assignment(second, versions[2])
        self.assertEqual(self.store.collection.overview()["assignments"], before)
        self.assignment(second, versions[2], code="PHY-OTHER")
        third, _ = self.plan(governance, second["protocol_id"])
        with self.assertRaises(Conflict):
            self.assignment(third, versions[2])

    def test_repeated_attempts_and_corrections_do_not_consume_new_distinct_versions(self):
        _, _, plan, assigned, receipt, _ = self.ready(limit=1)
        observations = []
        for _ in range(2):
            presentation = self.present(assigned, receipt)
            observation, _ = self.store.submit(
                presentation["presentation_id"], values(physician_code="PHY-QA")
            )
            observations.append(observation)
        correction = self.store.present(
            supersedes_response_id=observations[-1]["response_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )
        corrected, _ = self.store.submit(
            correction["presentation_id"],
            values(physician_code="PHY-QA", next_action="Fabricated correction"),
        )
        self.assertEqual(corrected["supersedes_response_id"], observations[-1]["response_id"])
        self.assertEqual(self.store.responses(), observations + [corrected])
        self.assertEqual(self.store.collection.overview()["assignments"], [assigned])
        other = next(
            record["version_id"]
            for record in self.store.catalog.overview()["versions"]
            if record["version_id"] != assigned["version_id"]
        )
        with self.assertRaises(Conflict):
            self.assignment(plan, other)

    def test_every_new_approved_scope_requires_new_notice_even_if_other_fields_unchanged(self):
        original, body = self.policy()
        self.assertEqual(self.governance.save(body), (original, True))
        revised = copy.deepcopy(body)
        revised.update(request_id=str(uuid4()), based_on_governance_id=original["governance_id"])
        with self.assertRaisesRegex(Conflict, "version"):
            self.governance.save(revised)
        revised["status"] = "draft"
        draft, _ = self.governance.save(revised)
        revised.update(
            request_id=str(uuid4()),
            based_on_governance_id=draft["governance_id"],
            status="approved",
        )
        with self.assertRaises(Conflict):
            self.governance.save(revised)
        revised["permission"]["version"] = "TEST-EXPLICIT-NEXT-SCOPE"
        self.governance.save(revised)

    def test_linked_plan_can_pin_legacy_governance_without_inventing_new_scope_fields(self):
        governance, _ = self.policy(legacy=True)
        plan, _ = self.plan(governance)
        assigned, _ = self.assignment(plan)
        self.record_review()
        receipt, _ = self.governance.permission(self.permission_body(governance))
        self.present(assigned, receipt)
        self.assertNotIn("session", governance)
        self.assertNotIn("professional_role", governance["operator"])
        self.assertEqual(self.store.collection.overview()["current"], plan)
        self.assertTrue(self.store.collection.overview()["readiness"]["governance_pin_current"])

    def test_new_notice_scope_gets_new_allowance_but_requires_new_permission(self):
        governance, body, plan, assigned, receipt, _ = self.ready(limit=1)
        different = next(
            item["version_id"]
            for item in self.store.catalog.overview()["versions"]
            if item["version_id"] != assigned["version_id"]
        )
        with self.assertRaises(Conflict):
            self.assignment(plan, different)
        next_body = copy.deepcopy(body)
        next_body.update(
            request_id=str(uuid4()), based_on_governance_id=governance["governance_id"]
        )
        next_body["permission"]["version"] = "TEST-NEW-EXPLICIT-NOTICE"
        new_governance, _ = self.governance.save(next_body)
        new_plan, _ = self.plan(new_governance, plan["protocol_id"])
        new_assignment, _ = self.assignment(new_plan, different)
        self.store.catalog.add_review(
            {
                "request_id": str(uuid4()),
                "version_id": different,
                "reviewer_code": "STF-QA",
                "reviewed_on": datetime.now(timezone.utc).date().isoformat(),
                "comments": "Fabricated review for explicit new scope.",
                "disposition": "approved",
                "supersedes_review_id": None,
            }
        )
        with self.assertRaises(Conflict):
            self.present(new_assignment, receipt)
        new_receipt, _ = self.governance.permission(self.permission_body(new_governance))
        self.present(new_assignment, new_receipt)
        with self.assertRaises(Conflict):
            self.assignment(new_plan, assigned["version_id"])
        exported = json.dumps(self.store.export(), ensure_ascii=False)
        for private in (
            body["permission"]["text"],
            body["session"]["description"],
            body["operator"]["professional_role"],
        ):
            self.assertNotIn(json.dumps(private, ensure_ascii=False), exported)
        self.assertEqual(
            Store(self.path).collection.overview()["assignments"], [assigned, new_assignment]
        )


if __name__ == "__main__":
    unittest.main()

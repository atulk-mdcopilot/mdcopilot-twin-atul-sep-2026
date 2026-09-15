"""Capture, corrections and ordinary-use gates across persistence modules."""

import json
import threading
import unittest
from datetime import datetime, timedelta
from uuid import uuid4

import test_governance as governance_tests
import test_http as http_tests
from helpers import values

from twin_lab.collection_schema import PROTOCOL_FIELDS
from twin_lab.schemas import Conflict, ValidationError, canonical_json, now, snapshot_hash
from twin_lab.server import make_server
from twin_lab.store import Store


class CaptureGovernanceTests(unittest.TestCase):
    setUp = governance_tests.GovernanceTests.setUp
    draft = staticmethod(governance_tests.GovernanceTests.draft)
    approved_body = governance_tests.GovernanceTests.approved_body
    create_plan = governance_tests.GovernanceTests.create_plan
    record_review = governance_tests.GovernanceTests.record_review
    permission_body = governance_tests.GovernanceTests.permission_body
    setup_human = governance_tests.GovernanceTests.setup_human

    def human_presentation(self, assignment, receipt):
        return self.store.present(
            assignment_id=assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )

    def human_response(self):
        governance, protocol, assignment, review, receipt = self.setup_human()
        presentation = self.human_presentation(assignment, receipt)
        response, _ = self.store.submit(
            presentation["presentation_id"], values(physician_code="PHY-QA")
        )
        return governance, protocol, assignment, review, receipt, presentation, response

    def legacy_records(self):
        snapshot = self.store.cases()[0]
        presentation = {
            "presentation_id": str(uuid4()),
            "presented_at": now(),
            "case_snapshot": snapshot,
            "snapshot_sha256": snapshot_hash(snapshot),
            "supersedes_response_id": None,
        }
        submitted = values(physician_code="LEGACY-QA")
        response = {
            "response_id": str(uuid4()),
            "presentation_id": presentation["presentation_id"],
            "physician_code": "LEGACY-QA",
            "case_id": snapshot["case_id"],
            "case_family": snapshot["family_id"],
            "case_version": snapshot["version"],
            "response_schema_version": "1.0",
            "case_snapshot": snapshot,
            "snapshot_sha256": presentation["snapshot_sha256"],
            "presented_at": presentation["presented_at"],
            "submitted_at": now(),
            "original_values": submitted,
            "normalized_values": {
                key: value.strip() if isinstance(value, str) else value
                for key, value in submitted.items()
            },
            "ai_advice_shown": False,
            "collection_purpose": "demo",
            "case_review_status": "unreviewed",
            "eligible_for_study": False,
            "supersedes_response_id": None,
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO presentations VALUES (?, ?)",
                (presentation["presentation_id"], canonical_json(presentation)),
            )
            db.execute(
                "INSERT INTO responses VALUES (?, ?, ?, ?)",
                (
                    response["response_id"],
                    presentation["presentation_id"],
                    None,
                    canonical_json(response),
                ),
            )
        return presentation, response

    def test_qa_requires_explicit_acknowledgment_and_retains_mode_after_restart(self):
        for changes in (
            {},
            {"capture_mode": "fabricated_qa"},
            {"capture_mode": "fabricated_qa", "qa_acknowledged": "true"},
            {
                "capture_mode": "fabricated_qa",
                "qa_acknowledged": True,
                "permission_receipt_id": str(uuid4()),
            },
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.store.present(case_id=self.store.cases()[0]["case_id"], **changes)
        presentation = self.store.present(
            case_id=self.store.cases()[0]["case_id"],
            capture_mode="fabricated_qa",
            qa_acknowledged=True,
        )
        response, _ = self.store.submit(presentation["presentation_id"], values())
        self.assertEqual(response["capture_mode"], "fabricated_qa")
        self.assertIsNone(response["permission_receipt_id"])
        self.assertIsNone(response["governance_id"])
        self.assertEqual(Store(self.path).responses(), [response])
        self.assertEqual(
            self.store.lifecycle.overview()["records"][0]["permission_status"], "fabricated_qa"
        )

    def test_human_metadata_exact_case_permission_and_retention_survive_restart(self):
        governance, _, assignment, review, receipt, presentation, response = self.human_response()
        self.assertEqual(response["case_snapshot"], presentation["case_snapshot"])
        self.assertEqual(response["case_version_id"], assignment["version_id"])
        self.assertEqual(response["case_review_id"], review["review_id"])
        self.assertEqual(response["governance_id"], governance["governance_id"])
        self.assertEqual(response["permission_receipt_id"], receipt["receipt_id"])
        self.assertEqual(response["permission_sha256"], receipt["permission_sha256"])
        self.assertEqual(response["capture_mode"], "physician_demo")
        self.assertEqual(Store(self.path).responses(), [response])
        with self.store.connection() as db:
            metadata = self.store.lifecycle.metadata(db, response["response_id"])
        self.assertEqual(metadata["retention_anchor_at"], response["submitted_at"])
        self.assertEqual(metadata["permission_status"], "recorded")
        self.assertIsNotNone(metadata["expires_at"])
        saved, duplicate = self.store.submit(
            presentation["presentation_id"], values(physician_code="PHY-QA")
        )
        self.assertTrue(duplicate)
        self.assertEqual(saved, response)

    def test_human_correction_preserves_receipt_original_values_and_retention_anchor(self):
        _, _, _, _, receipt, _, response = self.human_response()
        correction = self.store.present(
            supersedes_response_id=response["response_id"],
            capture_mode="physician_demo",
            permission_receipt_id=receipt["receipt_id"],
        )
        corrected, _ = self.store.submit(
            correction["presentation_id"],
            values(physician_code="PHY-QA", next_action="Fabricated correction"),
        )
        self.assertEqual(self.store.responses()[0], response)
        self.assertEqual(corrected["supersedes_response_id"], response["response_id"])
        for key in (
            "case_snapshot",
            "permission_receipt_id",
            "permission_version",
            "permission_sha256",
            "governance_id",
        ):
            self.assertEqual(corrected[key], response[key])
        with self.store.connection() as db:
            self.assertEqual(
                self.store.lifecycle.metadata(db, corrected["response_id"]),
                self.store.lifecycle.metadata(db, response["response_id"]),
            )

    def test_decline_after_presentation_prevents_save_and_after_save_prevents_retry(self):
        governance, _, assignment, _, receipt, _, response = self.human_response()
        pending = self.human_presentation(assignment, receipt)
        self.governance.permission(self.permission_body(governance, choice="decline"))
        for identifier in (pending["presentation_id"], response["presentation_id"]):
            with self.subTest(identifier=identifier), self.assertRaises(Conflict):
                self.store.submit(identifier, values(physician_code="PHY-QA"))
        self.assertEqual(self.store.responses(), [response])

    def test_governance_revocation_and_new_plan_prevent_human_retries(self):
        governance, protocol, assignment, _, _, _, response = self.human_response()
        self.governance.save(
            self.draft(
                based_on_governance_id=governance["governance_id"],
                status="revoked",
                approved_by_code="STF-QA",
                approval_note="Fabricated revocation.",
            )
        )
        with self.assertRaises(Conflict):
            self.store.submit(response["presentation_id"], values(physician_code="PHY-QA"))
        current = self.governance.overview()["current"]
        reopened, _ = self.governance.save(
            self.approved_body(based_on_governance_id=current["governance_id"])
        )
        receipt, _ = self.governance.permission(self.permission_body(reopened))
        pending = self.human_presentation(assignment, receipt)
        body = {key: protocol[key] for key in PROTOCOL_FIELDS}
        body.update(request_id=str(uuid4()), based_on_protocol_id=protocol["protocol_id"])
        self.store.collection.save_protocol(body)
        with self.assertRaises(Conflict):
            self.store.submit(pending["presentation_id"], values(physician_code="PHY-QA"))

    def test_withdrawal_hides_response_export_and_blocks_pending_save_retry_correction(self):
        _, _, assignment, _, receipt, _, response = self.human_response()
        pending = self.human_presentation(assignment, receipt)
        self.store.lifecycle.withdraw(
            {"request_id": str(uuid4()), "physician_code": "PHY-QA", "actor_code": "STF-QA"}
        )
        self.assertEqual(self.store.responses(), [])
        self.assertEqual(self.store.export()["responses"], [])
        for identifier in (pending["presentation_id"], response["presentation_id"]):
            with self.subTest(identifier=identifier), self.assertRaises(Conflict):
                self.store.submit(identifier, values(physician_code="PHY-QA"))
        with self.assertRaises(Conflict):
            self.store.present(
                supersedes_response_id=response["response_id"],
                capture_mode="physician_demo",
                permission_receipt_id=receipt["receipt_id"],
            )
        with self.store.connection() as db:
            self.assertEqual(
                json.loads(db.execute("SELECT payload FROM responses").fetchone()[0]), response
            )

    def test_expiry_and_hold_hide_retained_content_from_ordinary_use(self):
        _, _, _, _, receipt, _, response = self.human_response()
        with self.store.connection() as db:
            expires = self.store.lifecycle.metadata(db, response["response_id"])["expires_at"]
        original_clock = self.store.lifecycle.clock
        self.store.lifecycle.clock = lambda: (
            datetime.fromisoformat(expires) + timedelta(seconds=1)
        ).isoformat()
        self.assertEqual(self.store.responses(), [])
        self.assertEqual(self.store.export()["responses"], [])
        with self.assertRaises(Conflict):
            self.store.submit(response["presentation_id"], values(physician_code="PHY-QA"))
        self.store.lifecycle.clock = original_clock
        self.store.lifecycle.hold(
            {
                "request_id": str(uuid4()),
                "response_ids": [response["response_id"]],
                "actor_code": "STF-QA",
                "authority_record": "Fabricated hold authority.",
            }
        )
        self.assertEqual(self.store.responses(), [])
        self.assertEqual(self.store.export()["responses"], [])
        with self.assertRaises(Conflict):
            self.store.present(
                supersedes_response_id=response["response_id"],
                capture_mode="physician_demo",
                permission_receipt_id=receipt["receipt_id"],
            )

    def test_legacy_correction_cannot_reclassify_original_or_invent_permission(self):
        _, legacy = self.legacy_records()
        for mode, acknowledgment in (("fabricated_qa", True), ("physician_demo", False)):
            with self.subTest(mode=mode), self.assertRaises(Conflict):
                self.store.present(
                    supersedes_response_id=legacy["response_id"],
                    capture_mode=mode,
                    qa_acknowledged=acknowledgment,
                )
        correction = self.store.present(
            supersedes_response_id=legacy["response_id"], capture_mode="legacy_unclassified"
        )
        corrected, _ = self.store.submit(
            correction["presentation_id"], values(physician_code="LEGACY-QA")
        )
        self.assertEqual(corrected["capture_mode"], "legacy_unclassified")
        self.assertIsNone(corrected["permission_receipt_id"])
        self.assertEqual(self.store.responses()[0], legacy)
        self.assertNotIn("capture_mode", self.store.responses()[0])
        with self.store.connection() as db:
            self.assertEqual(
                self.store.lifecycle.metadata(db, corrected["response_id"])["permission_status"],
                "unknown_legacy",
            )
        with self.assertRaises(ValidationError):
            self.store.present(
                case_id=self.store.cases()[0]["case_id"], capture_mode="legacy_unclassified"
            )

    def test_stale_unsubmitted_presentation_requires_reopening(self):
        snapshot = self.store.cases()[0]
        presentation = {
            "presentation_id": str(uuid4()),
            "presented_at": now(),
            "case_snapshot": snapshot,
            "snapshot_sha256": snapshot_hash(snapshot),
            "supersedes_response_id": None,
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO presentations VALUES (?, ?)",
                (presentation["presentation_id"], canonical_json(presentation)),
            )
        with self.assertRaises(Conflict):
            self.store.submit(presentation["presentation_id"], values())
        self.assertEqual(self.store.responses(), [])

    def test_general_response_export_excludes_private_governance_registry(self):
        governance, _, _, _, _, _, response = self.human_response()
        export = self.store.export()
        self.assertEqual(export["responses"], [response])
        serialized = canonical_json(export)
        for private in (
            governance["operator"]["legal_name"],
            governance["operator"]["privacy_contact"],
            governance["owners"][0]["person_name"],
            governance["owners"][0]["contact"],
        ):
            self.assertNotIn(private, serialized)
        self.assertNotIn("permission_receipts", export)
        self.assertNotIn("governance_versions", export)


class CaptureGovernanceHttpTests(unittest.TestCase):
    draft = staticmethod(governance_tests.GovernanceTests.draft)
    approved_body = governance_tests.GovernanceTests.approved_body
    create_plan = governance_tests.GovernanceTests.create_plan
    record_review = governance_tests.GovernanceTests.record_review
    permission_body = governance_tests.GovernanceTests.permission_body
    request = http_tests.HttpTests.request
    stop_server = http_tests.HttpTests.stop_server

    def setUp(self):
        governance_tests.GovernanceTests.setUp(self)
        self.server = make_server(self.store, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def test_http_requires_explicit_mode_and_qa_acknowledgment(self):
        case_id = self.store.cases()[0]["case_id"]
        invalid = [
            {"case_id": case_id},
            {
                "case_id": case_id,
                "capture_mode": "fabricated_qa",
                "permission_receipt_id": None,
                "qa_acknowledged": False,
            },
            {
                "case_id": case_id,
                "capture_mode": "physician_demo",
                "permission_receipt_id": None,
                "qa_acknowledged": False,
            },
        ]
        for body in invalid:
            with self.subTest(body=body):
                status, _, _ = self.request("POST", "/api/presentations", body)
                self.assertEqual(status, 400)
        status, _, body = self.request("GET", "/api/governance")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["readiness"]["actual_physician_capture_enabled"])
        self.assertEqual(self.store.responses(), [])

    def test_http_approved_permission_copy_capture_and_decline_gate(self):
        self.create_plan()
        self.record_review()
        status, _, body = self.request("POST", "/api/governance", self.approved_body())
        self.assertEqual(status, 201)
        governance = json.loads(body)["governance"]
        status, _, body = self.request("POST", "/api/permissions", self.permission_body(governance))
        self.assertEqual(status, 201)
        receipt = json.loads(body)["receipt"]
        status, headers, copy = self.request("GET", f"/api/permissions/{receipt['receipt_id']}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(copy), receipt)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        assignment = self.store.collection.overview()["assignments"][0]
        status, _, body = self.request(
            "POST",
            "/api/presentations",
            {
                "assignment_id": assignment["assignment_id"],
                "capture_mode": "physician_demo",
                "permission_receipt_id": receipt["receipt_id"],
                "qa_acknowledged": False,
            },
        )
        self.assertEqual(status, 201)
        response_body = {
            "presentation_id": json.loads(body)["presentation_id"],
            "values": values(physician_code="PHY-QA"),
        }
        status, _, _ = self.request("POST", "/api/responses", response_body)
        self.assertEqual(status, 201)
        status, _, _ = self.request(
            "POST", "/api/permissions", self.permission_body(governance, choice="decline")
        )
        self.assertEqual(status, 201)
        status, _, _ = self.request("POST", "/api/responses", response_body)
        self.assertEqual(status, 409)

    def test_http_draft_or_forged_approval_cannot_issue_permission(self):
        body = self.draft(status="approved")
        status, _, _ = self.request("POST", "/api/governance", body)
        self.assertEqual(status, 400)
        status, _, _ = self.request("POST", "/api/governance", self.draft(training_allowed=True))
        self.assertEqual(status, 400)
        status, _, body = self.request("POST", "/api/governance", self.draft())
        self.assertEqual(status, 201)
        status, _, _ = self.request(
            "POST", "/api/permissions", self.permission_body(json.loads(body)["governance"])
        )
        self.assertEqual(status, 409)
        self.assertEqual(self.governance.overview()["receipts"], [])


if __name__ == "__main__":
    unittest.main()

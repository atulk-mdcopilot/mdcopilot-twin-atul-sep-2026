"""Deterministic fabricated fixtures and a small independent observation model."""

import hashlib
import json
import random
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from helpers import latest_version, values
from test_governance import GovernanceTests

from twin_lab.store import Store


class SequenceCase(unittest.TestCase):
    draft = staticmethod(GovernanceTests.draft)

    def start(self, seed, contract="1.0"):
        if hasattr(self, "trace"):
            self.write_trace()
        self.review = None
        self.contract = contract
        self.seed = seed
        self.rng = random.Random(seed)
        self.trace = []
        self.time = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
        self.expected = []
        self.payloads = {}
        self.visible = True
        self.expected_days = 7
        temporary = tempfile.TemporaryDirectory(prefix="twin-sequence-fabricated-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "twin-lab.sqlite3"
        stack = self.enterContext(ExitStack())
        case = self

        class ControlledDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return case.time.astimezone(tz) if tz else case.time.replace(tzinfo=None)

        class ControlledDate(date):
            @classmethod
            def today(cls):
                return case.time.date()

        for module in (
            "schemas",
            "store",
            "catalog",
            "collection",
            "governance",
            "lifecycle",
            "lifecycle_restore",
        ):
            stack.enter_context(patch(f"twin_lab.{module}.now", self.stamp))
        stack.enter_context(patch("twin_lab.governance_schema.datetime", ControlledDatetime))
        stack.enter_context(patch("twin_lab.catalog_schema.date", ControlledDate))
        self.addCleanup(self.write_trace)
        self.store = Store(self.path)
        self.version = latest_version(self.store.catalog.overview())
        self.code = f"SEQ-{seed}"
        self.note("fresh_database")

    def identifier(self):
        return str(UUID(int=self.rng.getrandbits(128), version=4))

    def stamp(self):
        return self.time.isoformat()

    def note(self, action, **details):
        self.trace.append({"action": action, "at": self.stamp(), **details})

    def evidence(self):
        return json.dumps(
            {"seed": self.seed, "contract": self.contract, "trace": self.trace}, sort_keys=True
        )

    def write_trace(self):
        # This mount belongs only to standalone quality Compose, never actual /data.
        output = Path("/quality-output")
        if output.is_dir():
            directory = output / "sequence-traces"
            directory.mkdir(exist_ok=True)
            (directory / f"{self._testMethodName}-{self.seed}.json").write_text(
                self.evidence() + "\n"
            )

    def approval_body(self, parent=None):
        body = GovernanceTests.approved_body(self, based_on_governance_id=parent)
        body["request_id"] = self.identifier()
        body["operator"]["pilot_close_date"] = "2026-09-30"
        body["permission"]["version"] = f"SEQ-PERM-{self.identifier()}"
        for owner in body["owners"]:
            owner["accepted_at"] = self.stamp()
        body["controls"]["checked_at"] = self.stamp()
        if self.contract == "2.0":
            body["governance_schema_version"] = "2.0"
            body["operator"].update(
                professional_role="Fabricated sequence role", pilot_start_date="2026-09-12"
            )
            body["session"] = {
                "description": "Fabricated case-set scope; repeated attempts are separate observations.",
                "max_distinct_case_versions": 2,
            }
            body["retention"].update(
                calendar_year_basis={
                    "pilot_close_date": "2026-09-30",
                    "anniversary_date": "2027-09-30",
                },
                permission_after_close_days=365,
                audit_after_close_days=365,
            )
        return body

    def setup_human(self):
        self.governance, _ = self.store.governance.save(self.approval_body())
        protocol = {
            "request_id": self.identifier(),
            "based_on_protocol_id": None,
            "title": "Fabricated sequence plan",
            "owner_code": "STF-QA",
            "physician_codes": [self.code],
            "consent_statement": "",
            "consent_version": "",
            "retention_days": None,
            "backup_owner_code": "",
            "backup_frequency": "manual_before_changes",
            "backup_retention_days": None,
            "notes": "Fabricated sequence only.",
        }
        if self.contract == "2.0":
            for key in (
                "consent_statement",
                "consent_version",
                "retention_days",
                "backup_retention_days",
            ):
                del protocol[key]
            protocol.update(
                protocol_schema_version="2.0", governance_id=self.governance["governance_id"]
            )
        self.protocol, _ = self.store.collection.save_protocol(protocol)
        self.assignment, _ = self.store.collection.assign(
            {
                "request_id": self.identifier(),
                "protocol_id": self.protocol["protocol_id"],
                "physician_code": self.code,
                "version_id": self.version["version_id"],
                "notes": "Fabricated sequence assignment.",
            }
        )
        self.review = self.review_version("approved")
        self.receipt = self.permission()
        self.note(
            "approve_plan_assign_agree",
            governance_id=self.governance["governance_id"],
            assignment_id=self.assignment["assignment_id"],
            receipt_id=self.receipt["receipt_id"],
        )

    def review_version(self, disposition):
        previous = getattr(self, "review", None)
        return self.store.catalog.add_review(
            {
                "request_id": self.identifier(),
                "version_id": self.version["version_id"],
                "reviewer_code": "STF-QA",
                "reviewed_on": self.time.date().isoformat(),
                "comments": "Fabricated sequence review.",
                "disposition": disposition,
                "supersedes_review_id": previous["review_id"] if previous else None,
            }
        )[0]

    def permission(self, choice="agree", governance=None):
        return self.store.governance.permission(
            {
                "request_id": self.identifier(),
                "governance_id": (governance or self.governance)["governance_id"],
                "physician_code": self.code,
                "choice": choice,
            }
        )[0]

    def present(self, previous=None):
        selector = (
            {"supersedes_response_id": previous["response_id"]}
            if previous
            else {"assignment_id": self.assignment["assignment_id"]}
        )
        return self.store.present(
            **selector,
            capture_mode="physician_demo",
            permission_receipt_id=self.receipt["receipt_id"],
        )

    def observe(self, previous=None):
        presentation = self.present(previous)
        answer = values(
            physician_code=self.code,
            next_action=f"  Fabricated seed {self.seed} action {len(self.expected)}.\n  ",
        )
        record, duplicate = self.store.submit(presentation["presentation_id"], answer)
        self.assertFalse(duplicate, self.evidence())
        self.assertEqual(record["original_values"], answer, self.evidence())
        self.assertEqual(record["physician_code"], self.code, self.evidence())
        self.assertEqual(record["submitted_at"], self.stamp(), self.evidence())
        self.assertEqual(record["case_snapshot"], presentation["case_snapshot"], self.evidence())
        encoded = json.dumps(
            presentation["case_snapshot"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(
            record["snapshot_sha256"],
            hashlib.sha256(encoded.encode()).hexdigest(),
            self.evidence(),
        )
        self.assertEqual(
            record["supersedes_response_id"],
            previous["response_id"] if previous else None,
            self.evidence(),
        )
        if previous:
            for key in (
                "case_snapshot",
                "case_version_id",
                "permission_receipt_id",
                "governance_id",
            ):
                self.assertEqual(record[key], previous[key], self.evidence())
        self.expected.append(record)
        with self.store.connection() as db:
            self.payloads[record["response_id"]] = db.execute(
                "SELECT payload FROM responses WHERE id=?", (record["response_id"],)
            ).fetchone()[0]
        self.note(
            "correct" if previous else "submit",
            response_id=record["response_id"],
            presentation_id=presentation["presentation_id"],
        )
        self.assert_model()
        return record

    def assert_model(self):
        self.assertEqual(
            self.store.responses(),
            self.expected if self.visible else [],
            self.evidence(),
        )
        self.assertEqual(
            self.store.export()["responses"],
            self.expected if self.visible else [],
            self.evidence(),
        )
        with self.store.connection() as db:
            actual = dict(db.execute("SELECT id,payload FROM responses ORDER BY rowid"))
            self.assertEqual(actual, self.payloads, self.evidence())
            roots = {row["response_id"]: row for row in self.expected}
            for record in self.expected:
                root = record
                while root["supersedes_response_id"]:
                    root = roots[root["supersedes_response_id"]]
                metadata = self.store.lifecycle.metadata(db, record["response_id"])
                expected_deadline = (
                    datetime.fromisoformat(root["submitted_at"])
                    + timedelta(days=self.expected_days)
                ).isoformat()
                self.assertEqual(
                    metadata["retention_anchor_at"],
                    root["submitted_at"],
                    self.evidence(),
                )
                self.assertEqual(metadata["expires_at"], expected_deadline, self.evidence())

    def restart(self):
        self.store = Store(self.path)
        self.note("restart")
        self.assert_model()

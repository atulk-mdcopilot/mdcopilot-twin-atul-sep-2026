"""Lifecycle operation sequences never resurrect a restricted response chain."""

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sequence_support import SequenceCase

from twin_lab.lifecycle_files import restore_snapshot
from twin_lab.schemas import Conflict
from twin_lab.store import Store


class LifecycleSequenceTests(SequenceCase):
    def test_backup_hold_withdraw_verify_release_expire_dispose_restore(self):
        self.start(5107)
        self.setup_human()
        original = self.observe()
        self.time += timedelta(minutes=1)
        correction = self.observe(original)
        exported, manifest = self.store.lifecycle.managed_export(self.store.export())
        self.assertEqual(exported["responses"], self.expected, self.evidence())
        backup_request = {"request_id": self.identifier()}
        backup, duplicate = self.store.collection.backup(backup_request)
        self.assertFalse(duplicate, self.evidence())
        # Explicitly retain an old synthetic snapshot to exercise journal reconciliation.
        detached = self.path.parent / "fabricated-old-snapshot.sqlite3"
        shutil.copyfile(self.path.parent / "backups" / backup["filename"], detached)
        self.assertEqual(
            self.store.collection.backup(backup_request),
            (backup, True),
            self.evidence(),
        )
        self.note(
            "backup_export",
            backup_id=backup["backup_id"],
            export_id=manifest["export_id"],
        )
        hold, _ = self.store.lifecycle.hold(
            {
                "request_id": self.identifier(),
                "response_ids": [correction["response_id"]],
                "actor_code": "STF-QA",
                "authority_record": "Fabricated hold authority.",
            }
        )
        self.visible = False
        self.note("hold_entire_chain")
        self.assert_model()
        self.time = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
        withdrawal, _ = self.store.lifecycle.withdraw(
            {
                "request_id": self.identifier(),
                "physician_code": self.code,
                "actor_code": "STF-QA",
            }
        )
        verification, _ = self.store.lifecycle.verify_withdrawal(
            {
                "request_id": self.identifier(),
                "withdrawal_id": withdrawal["withdrawal_id"],
                "actor_code": "STF-QA",
                "verification_attested": True,
                "withdrawal_days": None,
            }
        )
        self.assertEqual(
            verification["deadlines"],
            {original["response_id"]: "2026-09-19T12:00:00+00:00"},
            self.evidence(),
        )
        self.note("withdraw_verify")
        self.restart()
        with self.assertRaises(Conflict, msg=self.evidence()):
            self.store.submit(original["presentation_id"], original["original_values"])
        self.time = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
        held_plan = self.store.lifecycle.plan_disposal()
        self.assertEqual(held_plan["eligible_root_ids"], [], self.evidence())
        self.assertNotIn(manifest["export_id"], held_plan["export_ids"], self.evidence())
        self.assertNotIn(backup["backup_id"], held_plan["backup_ids"], self.evidence())
        self.store.lifecycle.release_hold(
            {
                "request_id": self.identifier(),
                "hold_id": hold["hold_id"],
                "actor_code": "STF-QA",
                "authority_record": "Fabricated release authority.",
            }
        )
        self.note("release_at_original_expiry")
        self.assert_model()
        plan = self.store.lifecycle.plan_disposal()
        self.assertEqual(plan["eligible_root_ids"], [original["response_id"]], self.evidence())
        self.assertIn(manifest["export_id"], plan["export_ids"], self.evidence())
        disposed = self.store.lifecycle.apply_disposal(plan, "STF-QA")
        self.assertEqual(disposed["disposed_root_ids"], [original["response_id"]], self.evidence())
        self.assertFalse(
            (self.path.parent / "exports" / manifest["filename"]).exists(),
            self.evidence(),
        )
        self.expected = []
        self.payloads = {}
        self.note("reviewed_fabricated_disposal")
        self.restart()
        destination = self.path.parent / "restored" / "twin-lab.sqlite3"
        restored_result = restore_snapshot(detached, destination, self.store.lifecycle.ledger_path)
        self.assertEqual(
            set(restored_result["removed_response_ids"]),
            {original["response_id"], correction["response_id"]},
            self.evidence(),
        )
        restored = Store(destination)
        self.assertEqual(restored.responses(), [], self.evidence())
        self.assertEqual(restored.export()["responses"], [], self.evidence())
        readiness = restored.governance.overview()["readiness"]
        self.assertIn("restore_reapproval_required", readiness["missing_fields"], self.evidence())
        with self.assertRaises(Conflict, msg=self.evidence()):
            restored.present(
                assignment_id=self.assignment["assignment_id"],
                capture_mode="physician_demo",
                permission_receipt_id=self.receipt["receipt_id"],
            )
        # Restoration cannot change or replace the current live file.
        self.assert_model()
        self.assertNotEqual(Path(restored_result["destination"]), self.path, self.evidence())
        self.note("sanitized_restore_requires_fresh_authority")
        self.time += timedelta(minutes=1)
        approved, _ = restored.governance.save(self.approval_body(self.governance["governance_id"]))
        fresh_code = f"{self.code}-FRESH"
        plan_body = {
            key: self.protocol[key]
            for key in (
                "request_id",
                "based_on_protocol_id",
                "title",
                "owner_code",
                "physician_codes",
                "consent_statement",
                "consent_version",
                "retention_days",
                "backup_owner_code",
                "backup_frequency",
                "backup_retention_days",
                "notes",
            )
        }
        plan_body.update(
            request_id=self.identifier(),
            based_on_protocol_id=self.protocol["protocol_id"],
            physician_codes=[fresh_code],
        )
        new_plan, _ = restored.collection.save_protocol(plan_body)
        new_assignment, _ = restored.collection.assign(
            {
                "request_id": self.identifier(),
                "protocol_id": new_plan["protocol_id"],
                "physician_code": fresh_code,
                "version_id": self.version["version_id"],
                "notes": "Fabricated post-restore assignment.",
            }
        )
        with self.assertRaises(Conflict, msg=self.evidence()):
            restored.present(
                assignment_id=new_assignment["assignment_id"],
                capture_mode="physician_demo",
                permission_receipt_id=self.receipt["receipt_id"],
            )
        fresh_receipt, _ = restored.governance.permission(
            {
                "request_id": self.identifier(),
                "governance_id": approved["governance_id"],
                "physician_code": fresh_code,
                "choice": "agree",
            }
        )
        presentation = restored.present(
            assignment_id=new_assignment["assignment_id"],
            capture_mode="physician_demo",
            permission_receipt_id=fresh_receipt["receipt_id"],
        )
        self.assertEqual(
            presentation["permission_receipt_id"],
            fresh_receipt["receipt_id"],
            self.evidence(),
        )
        self.assertEqual(restored.responses(), [], self.evidence())
        self.note("fresh_approval_plan_assignment_permission")

    def test_partial_restore_verification_keeps_its_original_clock_on_later_restore(
        self,
    ):
        self.start(7201)
        self.setup_human()
        # A long observation period isolates the shorter withdrawal deadline.
        body = self.approval_body(self.governance["governance_id"])
        body["retention"]["response_days"] = 60
        body["retention"]["after_close_days"] = 60
        self.governance, _ = self.store.governance.save(body)
        self.receipt = self.permission()
        self.expected_days = 60
        first = self.observe()
        early, _ = self.store.collection.backup({"request_id": self.identifier()})
        self.time += timedelta(hours=1)
        second = self.observe()
        later, _ = self.store.collection.backup({"request_id": self.identifier()})
        withdrawal, _ = self.store.lifecycle.withdraw(
            {
                "request_id": self.identifier(),
                "physician_code": self.code,
                "actor_code": "STF-QA",
            }
        )
        self.visible = False
        self.assert_model()
        partial_path = self.path.parent / "partial" / "twin-lab.sqlite3"
        restore_snapshot(
            self.path.parent / "backups" / early["filename"],
            partial_path,
            self.store.lifecycle.ledger_path,
        )
        partial = Store(partial_path)
        self.time = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
        verification, _ = partial.lifecycle.verify_withdrawal(
            {
                "request_id": self.identifier(),
                "withdrawal_id": withdrawal["withdrawal_id"],
                "actor_code": "STF-QA",
                "verification_attested": True,
                "withdrawal_days": None,
            }
        )
        deadline = "2026-09-21T12:00:00+00:00"
        self.assertEqual(
            verification["deadlines"], {first["response_id"]: deadline}, self.evidence()
        )
        self.assertEqual(
            verification["unavailable_root_ids"],
            [second["response_id"]],
            self.evidence(),
        )
        self.time += timedelta(days=2)
        full_path = self.path.parent / "full" / "twin-lab.sqlite3"
        restore_snapshot(
            self.path.parent / "backups" / later["filename"],
            full_path,
            partial.lifecycle.ledger_path,
        )
        full = Store(full_path)
        self.assertEqual(full.responses(), [], self.evidence())
        self.assertEqual(
            full.lifecycle.plan_disposal("2026-09-21T11:59:59+00:00")["eligible_root_ids"],
            [],
            self.evidence(),
        )
        self.assertEqual(
            set(full.lifecycle.plan_disposal(deadline)["eligible_root_ids"]),
            {first["response_id"], second["response_id"]},
            self.evidence(),
        )
        self.assertEqual(
            full.lifecycle.overview()["verifications"], [verification], self.evidence()
        )
        self.assert_model()
        self.note(
            "partial_verify_later_restore",
            deadline=deadline,
            absent_root=second["response_id"],
        )

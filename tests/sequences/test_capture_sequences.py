"""Seeded action sequences verify immutable observations and current authority."""

from datetime import datetime, timedelta, timezone

from helpers import values
from sequence_support import SequenceCase

from twin_lab.schemas import Conflict


class CaptureSequenceTests(SequenceCase):
    def test_seeded_capture_retry_correction_restart_export_model(self):
        for seed, contract in (
            (1701, "1.0"),
            (2048, "1.0"),
            (81103, "1.0"),
            (1702, "2.0"),
            (2049, "2.0"),
            (81104, "2.0"),
        ):
            with self.subTest(seed=seed, contract=contract):
                self.start(seed, contract)
                self.setup_human()
                latest = self.observe()
                for _ in range(3):
                    actions = ["retry", "correct", "new", "restart", "export"]
                    self.rng.shuffle(actions)
                    for action in actions:
                        self.time += timedelta(minutes=1)
                        self.note(action)
                        if action == "retry":
                            saved, duplicate = self.store.submit(
                                latest["presentation_id"], latest["original_values"]
                            )
                            self.assertTrue(duplicate, self.evidence())
                            self.assertEqual(saved, latest, self.evidence())
                            with self.assertRaises(Conflict, msg=self.evidence()):
                                self.store.submit(
                                    latest["presentation_id"],
                                    values(
                                        physician_code=self.code,
                                        next_action="Changed retry",
                                    ),
                                )
                        elif action == "correct":
                            latest = self.observe(latest)
                        elif action == "new":
                            latest = self.observe()
                        elif action == "restart":
                            self.restart()
                        else:
                            self.assertNotIn(
                                "permission_receipts",
                                self.store.export(),
                                self.evidence(),
                            )
                        self.assert_model()

    def test_present_then_authority_changes_rejects_save_after_restart(self):
        scenarios = [
            (contract, change)
            for contract in ("1.0", "2.0")
            for change in ("decline", "governance", "review", "close_boundary")
        ]
        for index, (contract, change) in enumerate(scenarios):
            with self.subTest(change=change, contract=contract):
                self.start(3100 + index, contract)
                self.setup_human()
                original = self.observe()
                pending = self.present()
                if change == "decline":
                    self.permission("decline")
                elif change == "governance":
                    self.store.governance.save(self.approval_body(self.governance["governance_id"]))
                elif change == "review":
                    self.review_version("rejected")
                else:
                    self.time = datetime(2026, 10, 1, tzinfo=timezone.utc)
                    self.visible = False  # Independent expected model: seven days elapsed.
                self.note("invalidate", cause=change)
                self.restart()
                for identifier in (
                    pending["presentation_id"],
                    original["presentation_id"],
                ):
                    with self.assertRaises(Conflict, msg=self.evidence()):
                        self.store.submit(identifier, original["original_values"])
                with self.assertRaises(Conflict, msg=self.evidence()):
                    self.present(original)
                self.assert_model()

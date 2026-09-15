"""Crash/retry guarantees use real SQLite commits and a real loopback HTTP request."""

import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from helpers import qa_presentation, values
from process_helpers import ChildBarrier, submit_http

from twin_lab.schemas import Conflict
from twin_lab.store import Store


class CaptureInterruptions(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="twin-interruption-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "capture.sqlite3"
        self.store = Store(self.path)
        self.presentation = self.store.present(
            **qa_presentation(case_id=self.store.cases()[0]["case_id"])
        )

    def payloads(self):
        with sqlite3.connect(self.path) as db:
            return dict(db.execute("SELECT id,payload FROM responses"))

    def submit_data(self):
        return {"presentation_id": self.presentation["presentation_id"], "values": values()}

    def test_insert_before_commit_is_absent_and_retry_commits_once(self):
        child = ChildBarrier(self, self.path, "response_before_commit", self.submit_data())
        child.kill_at_boundary()
        restarted = Store(self.path)
        self.assertEqual(self.payloads(), {})
        response, duplicate = restarted.submit(**self.submit_data())
        self.assertFalse(duplicate)
        same, duplicate = Store(self.path).submit(**self.submit_data())
        self.assertTrue(duplicate)
        self.assertEqual(same, response)
        self.assertEqual(response["case_snapshot"], self.presentation["case_snapshot"])
        self.assertEqual(response["original_values"], values())
        self.assertEqual(len(self.payloads()), 1)
        self.assertEqual(restarted.export()["responses"], [response])

    def test_commit_before_http_ack_survives_restart_and_exact_retry(self):
        child = ChildBarrier(self, self.path, "response_before_ack", {})
        port = child.receive()["port"]
        with ThreadPoolExecutor(max_workers=1) as requests:
            pending = requests.submit(submit_http, port, self.submit_data())
            child.kill_at_boundary()
            self.assertIn(
                pending.result(timeout=10), ("RemoteDisconnected", "ConnectionResetError")
            )
        original = self.payloads()
        self.assertEqual(len(original), 1)
        stored = json.loads(next(iter(original.values())))
        retried, duplicate = Store(self.path).submit(**self.submit_data())
        self.assertTrue(duplicate)
        self.assertEqual(retried, stored)
        self.assertEqual(self.payloads(), original)
        self.assertEqual(stored["snapshot_sha256"], self.presentation["snapshot_sha256"])
        self.assertEqual(stored["presented_at"], self.presentation["presented_at"])

    def test_durable_withdrawal_before_database_commit_stays_restricted(self):
        response, _ = self.store.submit(**self.submit_data())
        original = self.payloads()
        body = {"request_id": str(uuid4()), "physician_code": "DEMO_01", "actor_code": "FAULT_TEST"}
        child = ChildBarrier(
            self,
            self.path,
            "withdrawal_after_journal",
            {
                "body": body,
                "clock": "2026-09-12T12:00:00+00:00",
            },
        )
        child.kill_at_boundary()
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM lifecycle_events").fetchone()[0], 0)
        journal_path = self.path.parent / "lifecycle-events.jsonl"
        journal = journal_path.read_bytes()
        event = json.loads(journal)["event"]
        restarted = Store(self.path)
        self.assertEqual(restarted.responses(), [])
        self.assertEqual(restarted.export()["responses"], [])
        self.assertEqual(self.payloads(), original)
        with self.assertRaises(Conflict):
            restarted.submit(**self.submit_data())
        self.assertEqual(event["root_ids"], [response["response_id"]])
        recovered, duplicate = restarted.lifecycle.withdraw(body)
        self.assertFalse(duplicate)
        self.assertEqual(recovered, event)
        same, duplicate = Store(self.path).lifecycle.withdraw(body)
        self.assertTrue(duplicate)
        self.assertEqual(same, event)
        self.assertEqual(journal_path.read_bytes(), journal)
        self.assertEqual(self.payloads(), original)

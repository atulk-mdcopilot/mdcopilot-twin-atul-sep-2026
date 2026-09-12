"""Document approval records the user's decision without inventing operating facts."""

import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from twin_lab.governance import DOCUMENTS
from twin_lab.schemas import ValidationError
from twin_lab.server import make_server
from twin_lab.store import Store


class ApprovedDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(Path(self.temporary.name) / "twin-lab.sqlite3")

    def test_approved_documents_do_not_create_owners_receipts_or_operating_approval(self):
        overview = self.store.governance.overview()
        policy = overview["reference_documents"]["policy"]
        self.assertEqual(policy["document_status"], "approved")
        self.assertEqual(policy["permission"]["status"], "approved")
        self.assertEqual(policy["retention"]["status"], "approved")
        self.assertEqual(policy["approval"]["source"], "explicit_user_instruction")
        self.assertEqual(policy["approval"]["approved_by"], "project_user")
        self.assertIs(policy["permission"]["participant_ready"], False)
        self.assertTrue(all(value is None for value in policy["operator"].values()))
        self.assertTrue(all(owner["accepted_assignee"] is None for owner in policy["owner_registry"]))
        self.assertEqual(overview["history"], [])
        self.assertEqual(overview["receipts"], [])
        self.assertIs(overview["readiness"]["actual_physician_capture_enabled"], False)
        with self.assertRaises(ValidationError):
            self.store.governance.save(policy)
        self.assertEqual(self.store.responses(), [])

    def test_document_approval_preserves_policy_periods_and_disabled_scope(self):
        policy = self.store.governance.overview()["reference_documents"]["policy"]
        retention = policy["retention"]
        self.assertEqual(retention["RET-DEMO"]["max_days_from_anchor"], 90)
        self.assertEqual(retention["RET-DEMO"]["max_days_after_pilot_close"], 30)
        for record_class in ("RET-PERM", "RET-AUD"):
            self.assertEqual(retention[record_class]["years_after_pilot_close"], 1)
            self.assertNotIn("days_after_pilot_close", retention[record_class])
        for flag in ("actual_physician_response_capture_enabled", "training_allowed",
                     "research_reuse_allowed", "patient_data_allowed", "cloud_backup_allowed"):
            self.assertIs(policy["scope"][flag], False)

    def test_downloads_are_exact_approved_files_and_paths_are_allowlisted(self):
        server = make_server(self.store)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            reference = self.store.governance.overview()["reference_documents"]
            for item in reference["files"]:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                try:
                    connection.request("GET", item["url"])
                    result = connection.getresponse()
                    payload = result.read()
                    self.assertEqual(result.status, 200)
                    self.assertIn("attachment", result.getheader("Content-Disposition"))
                    self.assertEqual(payload, (DOCUMENTS / item["filename"]).read_bytes())
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), item["sha256"])
                finally:
                    connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            try:
                connection.request("GET", "/api/governance-documents/../../AGENTS.md")
                result = connection.getresponse()
                self.assertEqual(result.status, 404)
                self.assertIn("error", json.loads(result.read()))
            finally:
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

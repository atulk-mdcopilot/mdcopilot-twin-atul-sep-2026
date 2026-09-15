import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from helpers import latest_version, qa_presentation, values

from twin_lab.server import make_server
from twin_lab.store import Store


class ResourceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "img", "iframe", "audio", "video", "source"}:
            if attributes.get("src"):
                self.resources.append(attributes["src"])
        if tag == "link" and attributes.get("href"):
            self.resources.append(attributes["href"])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "http.sqlite3")
        self.server = make_server(self.store, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.origin = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path, data=None, headers=None, write_headers=True, raw=None):
        request_headers = {}
        if method == "POST" and write_headers:
            request_headers = {"Content-Type": "application/json", "X-Twin-Lab": "1"}
        request_headers.update(headers or {})
        body = (
            raw
            if raw is not None
            else (json.dumps(data).encode("utf-8") if data is not None else None)
        )
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            result = connection.getresponse()
            return result.status, dict(result.getheaders()), result.read()
        finally:
            connection.close()

    def present(self):
        case_id = self.store.cases()[0]["case_id"]
        status, _, body = self.request(
            "POST", "/api/presentations", qa_presentation(case_id=case_id)
        )
        self.assertIn(status, (200, 201))
        return json.loads(body)

    def test_http_case_save_review_retry_and_export_round_trip(self):
        status, _, body = self.request("GET", "/api/cases")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"cases": self.store.cases()})
        presentation = self.present()
        payload = {"presentation_id": presentation["presentation_id"], "values": values()}
        status, _, body = self.request(
            "POST", "/api/responses", payload, headers={"Origin": self.origin}
        )
        self.assertIn(status, (200, 201))
        saved = json.loads(body)
        self.assertFalse(saved["duplicate"])
        status, _, body = self.request("POST", "/api/responses", payload)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"response": saved["response"], "duplicate": True})
        status, _, body = self.request("GET", "/api/responses")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"responses": [saved["response"]]})
        status, headers, body = self.request("GET", "/api/export")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(json.loads(body)["responses"], [saved["response"]])

    def test_rejects_bad_host_origin_and_missing_write_guard(self):
        for host in ("evil.example", "127.0.0.1.evil.example", "localhost.evil.example"):
            with self.subTest(host=host):
                status, _, _ = self.request("GET", "/api/responses", headers={"Host": host})
                self.assertEqual(status, 403)
        for origin in ("https://evil.example", "null", "http://127.0.0.1:1"):
            with self.subTest(origin=origin):
                status, _, _ = self.request(
                    "POST", "/api/presentations", {}, headers={"Origin": origin}
                )
                self.assertEqual(status, 403)
        status, _, _ = self.request(
            "GET", "/api/responses", headers={"Sec-Fetch-Site": "cross-site"}
        )
        self.assertEqual(status, 403)
        status, _, _ = self.request(
            "POST",
            "/api/presentations",
            {},
            write_headers=False,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.store.responses(), [])

    def test_rejects_bad_content_type_oversize_or_ambiguous_json(self):
        status, _, _ = self.request(
            "POST", "/api/presentations", {}, headers={"Content-Type": "text/plain"}
        )
        self.assertEqual(status, 415)
        status, _, _ = self.request("POST", "/api/presentations", raw=b" " * 131073)
        self.assertEqual(status, 413)
        for payload in (
            b"{",
            b"[]",
            b'{"case_id":"a","case_id":"b"}',
            b'{"case_id":NaN}',
            b'{"case_id":Infinity}',
            b"\xff",
        ):
            with self.subTest(payload=payload):
                status, _, body = self.request("POST", "/api/presentations", raw=payload)
                self.assertEqual(status, 400)
                self.assertTrue(json.loads(body)["error"])

    def test_full_length_unicode_response_is_saved_exactly(self):
        presentation = self.present()
        submitted = values(
            next_action="🧪" * 5000,
            next_information="🔎" * 5000,
            decision_change="📝" * 5000,
            rationale="💬" * 5000,
        )
        raw = json.dumps(
            {"presentation_id": presentation["presentation_id"], "values": submitted},
            ensure_ascii=False,
        ).encode("utf-8")
        self.assertGreater(len(raw), 65536)
        status, _, body = self.request("POST", "/api/responses", raw=raw)
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["response"]["original_values"], submitted)
        self.assertEqual(self.store.responses()[0]["original_values"], submitted)

    def test_duplicate_keys_in_response_values_are_rejected_without_saving(self):
        presentation = self.present()
        raw = (
            '{"presentation_id":'
            + json.dumps(presentation["presentation_id"])
            + ',"values":'
            + json.dumps(values())[:-1]
            + ',"next_action":"Ambiguous second value"}}'
        ).encode("utf-8")
        status, _, body = self.request("POST", "/api/responses", raw=raw)
        self.assertEqual(status, 400)
        self.assertTrue(json.loads(body)["error"])
        self.assertEqual(self.store.responses(), [])

    def test_validation_missing_resources_and_conflict_have_clear_errors(self):
        presentation = self.present()
        payload = {
            "presentation_id": presentation["presentation_id"],
            "values": values(next_action=" "),
        }
        status, _, body = self.request("POST", "/api/responses", payload)
        self.assertEqual(status, 400)
        self.assertTrue(json.loads(body)["error"])
        self.assertEqual(self.store.responses(), [])
        status, _, _ = self.request(
            "POST", "/api/presentations", qa_presentation(case_id="missing")
        )
        self.assertEqual(status, 404)
        payload["values"] = values()
        self.request("POST", "/api/responses", payload)
        payload["values"] = values(next_action="Changed retry")
        status, _, body = self.request("POST", "/api/responses", payload)
        self.assertEqual(status, 409)
        self.assertTrue(json.loads(body)["error"])
        self.assertEqual(len(self.store.responses()), 1)

    def test_failed_persistence_returns_error_without_false_success_or_response_text(self):
        presentation = self.present()
        sensitive = "Synthetic test response must not appear in a failure log"
        connect = sqlite3.connect

        def readonly_connection(*args, **kwargs):
            return connect(f"file:{self.store.db_path}?mode=ro", uri=True)

        with patch("twin_lab.persistence.sqlite3.connect", side_effect=readonly_connection):
            with self.assertLogs(level="ERROR") as logs:
                status, _, body = self.request(
                    "POST",
                    "/api/responses",
                    {
                        "presentation_id": presentation["presentation_id"],
                        "values": values(next_action=sensitive),
                    },
                )
        self.assertEqual(status, 500)
        self.assertEqual(set(json.loads(body)), {"error"})
        self.assertTrue(json.loads(body)["error"])
        self.assertNotIn(sensitive.encode(), body)
        self.assertNotIn(sensitive, " ".join(logs.output))
        self.assertEqual(self.store.responses(), [])

    def test_new_review_version_plan_assignment_and_backup_routes_round_trip(self):
        status, _, raw = self.request("GET", "/api/catalog")
        self.assertEqual(status, 200)
        catalog = json.loads(raw)
        self.assertEqual(set(catalog), {"versions", "reviews", "families"})
        version = latest_version(catalog)
        review = {
            "request_id": str(uuid4()),
            "version_id": version["version_id"],
            "reviewer_code": "TEST",
            "reviewed_on": date.today().isoformat(),
            "comments": "Software test only.",
            "disposition": "approved",
            "supersedes_review_id": None,
        }
        snapshot = dict(
            version["snapshot"], version="test-http-2", narrative="Synthetic revised narrative."
        )
        revision = {
            "request_id": str(uuid4()),
            "based_on_version_id": version["version_id"],
            "version": "test-http-2",
            "editor_code": "TEST",
            "change_note": "Software test.",
            "snapshot": snapshot,
        }
        protocol = {
            "request_id": str(uuid4()),
            "based_on_protocol_id": None,
            "title": "Test draft",
            "owner_code": "",
            "physician_codes": ["DEMO_01"],
            "consent_statement": "",
            "consent_version": "",
            "retention_days": None,
            "backup_owner_code": "",
            "backup_frequency": "manual_before_changes",
            "backup_retention_days": None,
            "notes": "",
        }
        saved = {}
        for route, key, payload in (
            ("case-reviews", "review", review),
            ("case-versions", "version", revision),
            ("protocols", "protocol", protocol),
        ):
            status, _, raw = self.request("POST", "/api/" + route, payload)
            self.assertEqual(status, 201)
            record = json.loads(raw)
            self.assertEqual(set(record), {key, "duplicate"})
            self.assertFalse(record["duplicate"])
            saved[key] = record[key]
            status, _, raw = self.request("POST", "/api/" + route, payload)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw), {key: record[key], "duplicate": True})
        assignment = {
            "request_id": str(uuid4()),
            "protocol_id": saved["protocol"]["protocol_id"],
            "physician_code": "DEMO_01",
            "version_id": version["version_id"],
            "notes": "",
        }
        status, _, raw = self.request("POST", "/api/assignments", assignment)
        self.assertEqual(status, 201)
        assigned = json.loads(raw)["assignment"]
        status, _, raw = self.request(
            "POST", "/api/presentations", qa_presentation(assignment_id=assigned["assignment_id"])
        )
        self.assertEqual(status, 201)
        presentation = json.loads(raw)
        self.assertEqual(presentation["case_review_id"], saved["review"]["review_id"])
        status, _, raw = self.request(
            "POST",
            "/api/responses",
            {"presentation_id": presentation["presentation_id"], "values": values()},
        )
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(raw)["response"]["protocol_id"], assignment["protocol_id"])
        status, _, raw = self.request("POST", "/api/backups", {"request_id": str(uuid4())})
        self.assertEqual(status, 201)
        self.assertTrue(json.loads(raw)["backup"]["sha256"])
        status, _, raw = self.request("GET", "/api/collection")
        self.assertEqual(status, 200)
        overview = json.loads(raw)
        self.assertEqual(
            set(overview), {"current", "history", "assignments", "readiness", "backups"}
        )
        self.assertEqual(overview["assignments"], [assigned])
        self.assertIs(overview["readiness"]["study_collection_enabled"], False)

    def test_new_mutations_reject_missing_guard_and_forged_study_fields(self):
        for route in ("case-reviews", "case-versions", "protocols", "assignments", "backups"):
            with self.subTest(route=route):
                status, _, _ = self.request(
                    "POST",
                    "/api/" + route,
                    {},
                    write_headers=False,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 403)
                status, _, raw = self.request(
                    "POST",
                    "/api/" + route,
                    {"request_id": str(uuid4()), "study_collection_enabled": True},
                )
                self.assertEqual(status, 400)
                self.assertTrue(json.loads(raw)["error"])
        self.assertEqual(self.store.collection.overview()["history"], [])
        self.assertEqual(self.store.catalog.overview()["reviews"], [])

    def test_browser_shell_is_explicitly_synthetic_and_uses_only_local_resources(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        for notice in ("synthetic", "unreviewed", "validated clinical"):
            self.assertIn(notice, html.lower())
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        policy = headers["Content-Security-Policy"]
        self.assertIn("default-src 'none'", policy)
        self.assertIn("connect-src 'self'", policy)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        parser = ResourceParser()
        parser.feed(html)
        for resource in parser.resources:
            with self.subTest(resource=resource):
                parsed = urlsplit(resource)
                self.assertEqual(parsed.scheme, "")
                self.assertEqual(parsed.netloc, "")
                status, _, _ = self.request("GET", resource)
                self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()

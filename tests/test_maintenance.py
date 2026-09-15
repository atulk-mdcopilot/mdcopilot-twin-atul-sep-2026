"""Offline command boundary tests, using fabricated records in temporary storage."""

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from uuid import uuid4

from helpers import qa_presentation, values

from twin_lab.maintenance import main
from twin_lab.store import Store


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = Store(self.directory / "twin-lab.sqlite3")
        presentation = self.store.present(
            **qa_presentation(case_id=self.store.cases()[0]["case_id"])
        )
        self.response, _ = self.store.submit(presentation["presentation_id"], values())

    def run_command(self, *arguments):
        output = StringIO()
        with redirect_stdout(output):
            main(["--data-dir", str(self.directory), *map(str, arguments)])
        return json.loads(output.getvalue())

    def test_plan_never_overwrites_or_changes_responses_and_requires_exact_confirmation(self):
        path = self.directory / "twin-lab-disposal-plan.json"
        plan = self.run_command("plan", "--output", path)
        original = path.read_bytes()
        self.assertEqual(plan["eligible_root_ids"], [])
        for arguments in (
            ("plan", "--output", path),
            ("apply", "--plan", path, "--actor-code", "TEST", "--confirm", "wrong"),
        ):
            with (
                self.subTest(arguments=arguments),
                redirect_stderr(StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                self.run_command(*arguments)
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(self.store.responses(), [self.response])

    def test_restore_uses_new_destination_and_does_not_replace_live_database(self):
        backup, _ = self.store.collection.backup({"request_id": str(uuid4())})
        source = self.directory / "backups" / backup["filename"]
        destination = self.directory / "restored" / "twin-lab.sqlite3"
        result = self.run_command("restore", "--source", source, "--destination", destination)
        self.assertEqual(result["integrity_check"], "ok")
        self.assertEqual(Store(destination).responses(), [self.response])
        self.assertEqual(self.store.responses(), [self.response])
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            self.run_command("restore", "--source", source, "--destination", self.store.db_path)
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.store.responses(), [self.response])

    def test_missing_data_directory_does_not_create_empty_replacement_database(self):
        missing = self.directory / "missing"
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main(
                ["--data-dir", str(missing), "plan", "--output", str(self.directory / "plan.json")]
            )
        self.assertFalse(missing.exists())

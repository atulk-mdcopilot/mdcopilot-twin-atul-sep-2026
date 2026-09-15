"""Setup failures roll SQLite back; durable filesystem journals remain recoverable."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from historical_fixtures import historical_database, raw_rows

from twin_lab.catalog import Catalog
from twin_lab.lifecycle_files import initialize_journals
from twin_lab.store import Store


def schema_rows(path):
    with sqlite3.connect(path) as db:
        return db.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()


class SetupAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "historical.sqlite3"

    def before_setup(self, version):
        if version:
            historical_database(self.path, version)
        else:
            with sqlite3.connect(self.path):
                pass
        return raw_rows(self.path), schema_rows(self.path)

    def assert_rolled_back_then_recover(self, before, version):
        self.assertEqual(raw_rows(self.path), before[0])
        self.assertEqual(schema_rows(self.path), before[1])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], version)
        Store(self.path)
        completed = raw_rows(self.path)
        Store(self.path)
        self.assertEqual(raw_rows(self.path), completed)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 4)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_ddl_failure_rolls_back_the_whole_ordered_setup(self):
        original_connect = sqlite3.connect

        class FailAfterPermissionTable(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                result = super().execute(sql, *args, **kwargs)
                if "CREATE TABLE IF NOT EXISTS permission_receipts" in " ".join(sql.split()):
                    raise sqlite3.OperationalError("Fabricated failure after permission table DDL")
                return result

        def connect(*args, **kwargs):
            return original_connect(*args, **dict(kwargs, factory=FailAfterPermissionTable))

        for version in (0, 1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                self.path = Path(directory) / "historical.sqlite3"
                before = self.before_setup(version)
                with patch("sqlite3.connect", side_effect=connect):
                    with self.assertRaisesRegex(sqlite3.OperationalError, "Fabricated failure"):
                        Store(self.path)
                self.assert_rolled_back_then_recover(before, version)

    def test_seed_failure_does_not_mark_partial_initialization_complete(self):
        before = self.before_setup(1)
        original_seed = Catalog._seed_wording_revision

        def fail_after_seed(catalog, db):
            original_seed(catalog, db)
            raise OSError("Fabricated failure after source seeding")

        with patch.object(Catalog, "_seed_wording_revision", fail_after_seed):
            with self.assertRaisesRegex(OSError, "after source seeding"):
                Store(self.path)
        self.assert_rolled_back_then_recover(before, 1)

    def test_journal_failure_preserves_files_but_rolls_back_database_and_marker(self):
        before = self.before_setup(2)

        def fail_after_journals(lifecycle, db):
            initialize_journals(lifecycle, db)
            raise OSError("Fabricated failure after durable journal initialization")

        with patch("twin_lab.lifecycle_files.initialize_journals", fail_after_journals):
            with self.assertRaisesRegex(OSError, "durable journal initialization"):
                Store(self.path)
        for name in ("deletion-ledger.jsonl", "lifecycle-events.jsonl"):
            self.assertEqual((self.path.parent / name).read_bytes(), b"")
        self.assert_rolled_back_then_recover(before, 2)

    def test_concurrent_version_advance_before_lock_is_not_downgraded(self):
        before = self.before_setup(2)
        original_connect = sqlite3.connect
        path = self.path

        class ConcurrentVersionConnection(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                if sql == "BEGIN IMMEDIATE":
                    # Another binary finishes its upgrade just before this
                    # connection acquires the write lock. No timing assumptions.
                    with original_connect(path) as concurrent:
                        concurrent.execute("PRAGMA user_version = 99")
                return super().execute(sql, *args, **kwargs)

        def connect(*args, **kwargs):
            return original_connect(*args, **dict(kwargs, factory=ConcurrentVersionConnection))

        with patch("sqlite3.connect", side_effect=connect):
            with self.assertRaisesRegex(RuntimeError, "Unsupported database version"):
                Store(self.path)
        self.assertEqual(raw_rows(self.path), before[0])
        self.assertEqual(schema_rows(self.path), before[1])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 99)
        self.assertEqual(list(self.path.parent.glob("*.jsonl")), [])


if __name__ == "__main__":
    unittest.main()

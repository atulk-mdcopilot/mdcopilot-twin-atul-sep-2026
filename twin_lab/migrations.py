"""Ordered, atomic SQLite setup for the supported historical database shapes.

Fixture seeding and journal initialization are separate operations participating
in this transaction. Journal files have their own durability boundary: rollback
does not remove them. Contract version 4 retains all existing payload bytes.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from .schemas import Record

if TYPE_CHECKING:
    from .store import Store

DATABASE_VERSION = 4
RESTORE_BARRIER_DDL = """CREATE TABLE IF NOT EXISTS restore_barriers (
    id TEXT PRIMARY KEY, payload TEXT NOT NULL)"""
LIFECYCLE_EVENTS_DDL = """CREATE TABLE IF NOT EXISTS lifecycle_events (
    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL,
    request_body TEXT NOT NULL, payload TEXT NOT NULL)"""


def _append_only(db: sqlite3.Connection, tables: tuple[str, ...]) -> None:
    # Every table identifier comes from the constant schema declarations below.
    for table in tables:
        for operation in ("UPDATE", "DELETE"):
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{operation}
                BEFORE {operation} ON {table} BEGIN
                SELECT RAISE(ABORT, 'Append-only records'); END""")


def _capture_schema(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS presentations (
        id TEXT PRIMARY KEY, payload TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS responses (
        id TEXT PRIMARY KEY,
        presentation_id TEXT NOT NULL UNIQUE REFERENCES presentations(id),
        supersedes_id TEXT UNIQUE REFERENCES responses(id), payload TEXT NOT NULL)""")
    _append_only(db, ("presentations", "responses"))


def _catalog_and_collection_schema(db: sqlite3.Connection) -> None:
    statements = (
        """CREATE TABLE IF NOT EXISTS case_versions (
            id TEXT PRIMARY KEY, case_id TEXT NOT NULL, version_label TEXT NOT NULL,
            based_on_id TEXT UNIQUE REFERENCES case_versions(id),
            request_id TEXT UNIQUE, request_body TEXT, payload TEXT NOT NULL,
            UNIQUE(case_id, version_label))""",
        """CREATE TABLE IF NOT EXISTS case_reviews (
            id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES case_versions(id),
            supersedes_id TEXT UNIQUE REFERENCES case_reviews(id),
            request_id TEXT NOT NULL UNIQUE, request_body TEXT NOT NULL, payload TEXT NOT NULL)""",
        "CREATE TABLE IF NOT EXISTS case_families (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
        "CREATE INDEX IF NOT EXISTS case_reviews_version ON case_reviews(version_id)",
        """CREATE TABLE IF NOT EXISTS collection_protocols (
            id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
            request_body TEXT NOT NULL, payload TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS case_assignments (
            id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
            protocol_id TEXT NOT NULL REFERENCES collection_protocols(id),
            physician_code TEXT NOT NULL, version_id TEXT NOT NULL REFERENCES case_versions(id),
            request_body TEXT NOT NULL, payload TEXT NOT NULL,
            UNIQUE(protocol_id, physician_code, version_id))""",
        "CREATE TABLE IF NOT EXISTS local_backups (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    )
    for statement in statements:
        db.execute(statement)
    _append_only(
        db,
        (
            "case_versions",
            "case_reviews",
            "case_families",
            "collection_protocols",
            "case_assignments",
            "local_backups",
        ),
    )


def _governance_and_lifecycle_schema(db: sqlite3.Connection) -> None:
    statements = (
        """CREATE TABLE IF NOT EXISTS governance_versions (
            id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
            request_body TEXT NOT NULL, payload TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS permission_receipts (
            id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
            governance_id TEXT NOT NULL REFERENCES governance_versions(id),
            physician_code TEXT NOT NULL, request_body TEXT NOT NULL, payload TEXT NOT NULL)""",
        RESTORE_BARRIER_DDL,
        "CREATE TABLE IF NOT EXISTS lifecycle_state (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS response_lifecycle (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
        LIFECYCLE_EVENTS_DDL,
        "CREATE TABLE IF NOT EXISTS managed_exports (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    )
    for statement in statements:
        db.execute(statement)
    _append_only(
        db,
        (
            "governance_versions",
            "permission_receipts",
            "restore_barriers",
            "response_lifecycle",
            "lifecycle_events",
            "managed_exports",
        ),
    )


SETUP_STEPS = (
    _capture_schema,
    _catalog_and_collection_schema,
    _governance_and_lifecycle_schema,
)


def initialize(store: Store, cases: list[Record], *, include_families: bool) -> None:
    from .lifecycle_files import initialize_journals

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2, 3, DATABASE_VERSION):
            raise RuntimeError("Unsupported database version; keep the original database.")
        # Reapply idempotent declarations even on current-version startup. This preserves the
        # established recovery behavior for historical partially initialized DBs.
        for setup in SETUP_STEPS:
            setup(db)
        store.catalog.initialize(cases, include_families=include_families, db=db)
        initialize_journals(store.lifecycle, db)
        db.execute(f"PRAGMA user_version = {DATABASE_VERSION}")

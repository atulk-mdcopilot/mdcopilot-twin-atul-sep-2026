"""Small SQLite primitives; callers own domain validation and transaction scope."""

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .schemas import Conflict, NotFound, Record

# These are internal application tables, never request-controlled SQL identifiers.
TABLES = frozenset(
    {
        "presentations",
        "responses",
        "case_versions",
        "case_reviews",
        "case_families",
        "collection_protocols",
        "case_assignments",
        "local_backups",
        "governance_versions",
        "permission_receipts",
        "restore_barriers",
        "response_lifecycle",
        "lifecycle_events",
        "managed_exports",
    }
)


def _table(table: str) -> str:
    if table not in TABLES:
        raise ValueError("Unknown internal persistence table.")
    return table


@contextmanager
def connection(path: Path) -> Iterator[sqlite3.Connection]:
    """Commit on successful exit, roll back on failure, and always close the handle."""
    db = sqlite3.connect(path, timeout=5)
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA synchronous = FULL")
        with db:
            yield db
    finally:
        db.close()


def get_record(
    db: sqlite3.Connection,
    table: str,
    identifier: str,
    *,
    missing: str = "The requested local record was not found.",
    decode: Callable[[str], Record] = json.loads,
) -> Record:
    row = db.execute(f"SELECT payload FROM {_table(table)} WHERE id = ?", (identifier,)).fetchone()
    if row is None:
        raise NotFound(missing)
    return decode(row[0])


def read_records(db: sqlite3.Connection, table: str) -> list[Record]:
    return [
        json.loads(row[0])
        for row in db.execute(f"SELECT payload FROM {_table(table)} ORDER BY rowid")
    ]


def find_retry(
    db: sqlite3.Connection,
    table: str,
    request_id: str,
    request_body: str,
    *,
    conflict: str = "This request was already saved with different values. Refresh the history.",
    decode: Callable[[str], Record] = json.loads,
) -> Record | None:
    row = db.execute(
        f"SELECT request_body, payload FROM {_table(table)} WHERE request_id = ?", (request_id,)
    ).fetchone()
    if row is None:
        return None
    if row[0] != request_body:
        raise Conflict(conflict)
    return decode(row[1])

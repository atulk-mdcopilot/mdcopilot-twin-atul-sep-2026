"""Verified local SQLite snapshots. Live database replacement is not exposed."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .schemas import canonical_json, exact_keys, validate_id


def _lifecycle_manifest(db, created_at):
    """Copy deadlines derive from the snapshot's frozen policies, never today's draft."""
    from .lifecycle import instant
    responses = {row[0]: json.loads(row[1]) for row in db.execute("SELECT id,payload FROM responses")}
    roots = sorted(identifier for identifier, row in responses.items() if not row["supersedes_response_id"])
    has_metadata = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='response_lifecycle'").fetchone()
    metadata = {row[0]: json.loads(row[1]) for row in db.execute("SELECT id,payload FROM response_lifecycle")} if has_metadata else {}
    deadlines, grace = [], {}
    for root in roots:
        record = metadata.get(root)
        if record and record.get("policy"):
            policy = record["policy"]
            grace[root] = policy["backup_after_deletion_days"]
            deadlines.extend((instant(created_at) + timedelta(days=policy["backup_days"]),
                              instant(record["expires_at"]) + timedelta(days=policy["backup_after_deletion_days"])))
    return {"source_root_ids": roots, "source_backup_grace_days": grace,
            "expires_at": min(deadlines).isoformat() if deadlines else None,
            "unknown_policy_root_ids": [root for root in roots if root not in grace],
            "restore_requires_authoritative_lifecycle_journals": True}


def create_backup(store, body):
    exact_keys(body, {"request_id"})
    request_id = validate_id(body["request_id"])
    directory = store.db_path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / f"twin-lab-{request_id}.sqlite3"
    with store.connection() as gate:
        gate.execute("BEGIN IMMEDIATE")
        existing = gate.execute("SELECT payload FROM local_backups WHERE id = ?", (request_id,)).fetchone()
        if existing:
            record = json.loads(existing[0])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise RuntimeError("The saved backup file is missing or changed. Create a new backup.")
            return record, True
        if not path.exists():
            fd, temporary_name = tempfile.mkstemp(prefix=".snapshot-", suffix=".sqlite3", dir=directory)
            os.close(fd)
            temporary = Path(temporary_name)
            try:
                # The reserved write lock prevents changes while a separate read-only
                # connection copies the last committed database. No write-transaction
                # connection is passed to backup(), which could otherwise block itself.
                source = sqlite3.connect(store.db_path.resolve().as_uri() + "?mode=ro", uri=True)
                target = sqlite3.connect(temporary)
                try:
                    source.backup(target)
                    if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                        raise RuntimeError("SQLite backup integrity check failed.")
                finally:
                    target.close()
                    source.close()
                temporary.chmod(0o600)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        # A previous process may have completed the rename before its manifest
        # committed. The same request recovers that immutable snapshot, not a new one.
        check = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            if check.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise RuntimeError("SQLite backup integrity check failed.")
            created_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            lifecycle = _lifecycle_manifest(check, created_at)
        finally:
            check.close()
        # Flush the completed file and its directory entry before recording
        # success. This also covers a retry after an interrupted rename.
        with path.open("rb") as saved_file:
            os.fsync(saved_file.fileno())
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        contents = path.read_bytes()
        record = {"backup_id": request_id,
                  "created_at": created_at,
                  "filename": path.name, "sha256": hashlib.sha256(contents).hexdigest(),
                  "size_bytes": len(contents), **lifecycle}
        gate.execute("INSERT INTO local_backups(id, payload) VALUES (?, ?)",
                     (request_id, canonical_json(record)))
    return record, False

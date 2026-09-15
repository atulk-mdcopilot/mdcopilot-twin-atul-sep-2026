"""Offline disposal and restore; no live-database replacement path."""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4

from .lifecycle_files import ledger_entries, restriction_entries, sync_directory
from .migrations import LIFECYCLE_EVENTS_DDL, RESTORE_BARRIER_DDL
from .schemas import ValidationError, now


def purge_roots(db, root_ids):
    """Explicit exception to append-only capture, inside the caller's transaction."""
    records = [
        (row[0], row[1], json.loads(row[2]))
        for row in db.execute("SELECT id,presentation_id,payload FROM responses ORDER BY rowid")
    ]
    selected = set(root_ids)
    changed = True
    while changed:
        additions = {
            identifier
            for identifier, _, payload in records
            if payload.get("supersedes_response_id") in selected
        } - selected
        changed = bool(additions)
        selected.update(additions)
    presentation_ids = {
        presentation_id for identifier, presentation_id, _ in records if identifier in selected
    }
    presentation_ids.update(
        row[0]
        for row in db.execute("SELECT id,payload FROM presentations")
        if json.loads(row[1]).get("supersedes_response_id") in selected
    )
    # Capture SQL first. SQLite transactional DDL restores the protections if any
    # statement fails; only DELETE triggers are temporarily suspended.
    triggers = db.execute("""SELECT name,sql FROM sqlite_master WHERE type='trigger'
        AND name IN ('responses_no_DELETE','presentations_no_DELETE')""").fetchall()
    for name, _ in triggers:
        db.execute(f'DROP TRIGGER "{name}"')
    for identifier, _, _ in reversed(records):
        if identifier in selected:
            db.execute("DELETE FROM responses WHERE id=?", (identifier,))
    for identifier in presentation_ids:
        db.execute("DELETE FROM presentations WHERE id=?", (identifier,))
    for _, statement in triggers:
        db.execute(statement)
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Disposal would violate database references.")
    return {"response_ids": sorted(selected), "presentation_ids": sorted(presentation_ids)}


def restore_snapshot(source, destination, ledger_path):
    source, destination, ledger_path = Path(source), Path(destination), Path(ledger_path)
    if destination.exists() or destination.is_symlink():
        raise ValidationError(
            "Restore requires a new destination; existing files cannot be replaced."
        )
    if not source.is_file() or not ledger_path.is_file():
        raise ValidationError(
            "A backup and the authoritative external deletion ledger are required."
        )
    entries = ledger_entries(ledger_path)
    restrictions = restriction_entries(ledger_path.parent)
    roots = {root for entry in entries for root in entry["root_ids"]}
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, name = tempfile.mkstemp(
        prefix=".restore-", suffix=".sqlite3", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        incoming = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
        restored = sqlite3.connect(temporary)
        try:
            if incoming.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise RuntimeError("Backup integrity check failed.")
            incoming.backup(restored)
            restored.execute("PRAGMA foreign_keys=ON")
            restored.execute("PRAGMA synchronous=FULL")
            restored.execute("PRAGMA secure_delete=ON")
            with restored:
                restored.execute("BEGIN IMMEDIATE")
                removed = purge_roots(restored, roots)
                restored.execute(LIFECYCLE_EVENTS_DDL)
                for item in restrictions:
                    event = item["event"]
                    existing = restored.execute(
                        "SELECT request_body FROM lifecycle_events WHERE request_id=?",
                        (item["request_id"],),
                    ).fetchone()
                    if existing and existing[0] != item["request_body"]:
                        raise RuntimeError("Backup and authoritative lifecycle journal conflict.")
                    if not existing:
                        restored.execute(
                            "INSERT INTO lifecycle_events VALUES (?,?,?,?,?)",
                            (
                                event["event_id"],
                                item["request_id"],
                                event["kind"],
                                item["request_body"],
                                json.dumps(event, ensure_ascii=False),
                            ),
                        )
                restored.execute(RESTORE_BARRIER_DDL)
                barrier = {"restore_id": str(uuid4()), "restored_at": now()}
                restored.execute(
                    "INSERT INTO restore_barriers VALUES (?,?)",
                    (barrier["restore_id"], json.dumps(barrier)),
                )
            restored.execute("VACUUM")
            if restored.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise RuntimeError("Restored database integrity check failed.")
        finally:
            restored.close()
            incoming.close()
        temporary.chmod(0o600)
        with temporary.open("rb") as output:
            os.fsync(output.fileno())
        for name in ("deletion-ledger.jsonl", "lifecycle-events.jsonl"):
            authoritative = (
                ledger_path if name == "deletion-ledger.jsonl" else ledger_path.parent / name
            )
            target = destination.parent / name
            contents = authoritative.read_bytes()
            if target.exists():
                if target.read_bytes() != contents:
                    raise ValidationError(
                        "The destination contains different lifecycle journals. Use a new restore directory."
                    )
            else:
                with target.open("xb") as output:
                    target.chmod(0o600)
                    output.write(contents)
                    output.flush()
                    os.fsync(output.fileno())
        # Hard-linking refuses overwrite even if another process creates the target
        # after the existence check. The sanitized database is first visible here.
        os.link(temporary, destination)
        sync_directory(destination.parent)
        return {
            "destination": str(destination),
            "ledger_entries_applied": len(entries),
            "restriction_events_applied": len(restrictions),
            "removed_response_ids": removed["response_ids"],
            "integrity_check": "ok",
            "forensic_erasure_claimed": False,
        }
    finally:
        temporary.unlink(missing_ok=True)

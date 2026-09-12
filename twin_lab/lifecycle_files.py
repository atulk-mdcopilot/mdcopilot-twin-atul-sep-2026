"""Managed local copies, explicit disposal plans, and authoritative restore ledger."""

from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from .lifecycle import instant
from .schemas import Conflict, ValidationError, canonical_json, validate_code, validate_id


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def initialize_journals(lifecycle, db):
    db.execute("CREATE TABLE IF NOT EXISTS lifecycle_state (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    initialized = db.execute("SELECT 1 FROM lifecycle_state WHERE id='journals_initialized'").fetchone()
    for name in ("deletion-ledger.jsonl", "lifecycle-events.jsonl"):
        path = lifecycle.store.db_path.parent / name
        if initialized and not path.is_file():
            raise RuntimeError("An authoritative lifecycle journal is missing. Restore it before opening this database.")
        if not path.exists():
            with path.open("x", encoding="utf-8") as output:
                path.chmod(0o600)
                output.flush()
                os.fsync(output.fileno())
            sync_directory(path.parent)
    ledger_entries(lifecycle.ledger_path)
    restriction_entries(lifecycle.ledger_path.parent)
    db.execute("INSERT OR IGNORE INTO lifecycle_state VALUES ('journals_initialized','true')")


def ledger_entries(path):
    path = Path(path)
    if not path.exists():
        raise RuntimeError("The authoritative deletion ledger is missing.")
    # An interrupted or malformed ledger is an error, never permission to reuse data.
    try:
        entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry["root_ids"], list):
                raise ValueError
            instant(entry["deleted_at"])
            validate_id(entry["entry_id"])
            validate_code(entry["actor_code"])
            for identifier in entry["root_ids"]:
                validate_id(identifier)
        return entries
    except (ValueError, TypeError, AttributeError, KeyError, UnicodeError) as exc:
        raise RuntimeError("Deletion ledger is invalid; recover the authoritative ledger before continuing.") from exc


def restriction_entries(directory):
    path = Path(directory) / "lifecycle-events.jsonl"
    if not path.exists():
        raise RuntimeError("The authoritative lifecycle journal is missing.")
    try:
        entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for item in entries:
            validate_id(item["request_id"])
            body, event = json.loads(item["request_body"]), item["event"]
            validate_id(event["event_id"])
            validate_code(event["actor_code"])
            instant(event["recorded_at"])
            kind = event["kind"]
            if kind not in ("withdrawal", "verification", "hold", "hold_release") or body["event_kind"] != kind:
                raise ValueError
            if kind == "withdrawal":
                validate_code(event["physician_code"])
                validate_id(event["withdrawal_id"])
            if kind in ("withdrawal", "hold"):
                if not isinstance(event["root_ids"], list):
                    raise ValueError
                for identifier in event["root_ids"]:
                    validate_id(identifier)
            if kind in ("hold", "hold_release"):
                validate_id(event["hold_id"])
            if kind == "verification":
                validate_id(event["withdrawal_id"])
                instant(event["verified_at"])
                days = event.get("withdrawal_days")
                if days is not None and (type(days) is not int or not 1 <= days <= 3650):
                    raise ValueError
                if not isinstance(event["deadlines"], dict):
                    raise ValueError
                for identifier, deadline in event["deadlines"].items():
                    validate_id(identifier)
                    instant(deadline)
        return entries
    except (ValueError, TypeError, AttributeError, KeyError, UnicodeError) as exc:
        raise RuntimeError("The authoritative lifecycle journal is invalid; recover it before continuing.") from exc


def append_ledger(path, entry):
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as output:
        output.write(canonical_json(entry) + "\n")
        output.flush()
        os.fsync(output.fileno())
    sync_directory(path.parent)


def _file_path(lifecycle, kind, manifest):
    directory = lifecycle.store.db_path.parent / ("exports" if kind == "exports" else "backups")
    name = manifest["filename"]
    if Path(name).name != name or name in (".", ".."):
        raise RuntimeError("Unsafe managed-copy manifest filename.")
    return directory / name


def inventory(lifecycle, db, at=None):
    timestamp = instant(at or lifecycle.clock())
    roots = {lifecycle.root_for(db, row[0])["response_id"] for row in db.execute("SELECT id FROM responses")}
    restrictions = {root: lifecycle.restriction(db, root, at) for root in roots}
    ledger = ledger_entries(lifecycle.ledger_path)
    disposed = {}
    for item in ledger:
        for root in item["root_ids"]:
            timestamp_deleted = instant(item["deleted_at"])
            disposed[root] = min(disposed.get(root, timestamp_deleted), timestamp_deleted)
    result = {}
    for kind, table in (("exports", "managed_exports"), ("backups", "local_backups")):
        copies = []
        for original in lifecycle.rows(db, table):
            item = dict(original)
            source_ids = item.get("source_root_ids", [])
            item["held"] = any(restrictions.get(root) == "legal_hold" for root in source_ids)
            item["restricted_sources"] = [root for root in source_ids if restrictions.get(root) or root in disposed]
            deadline = instant(item["expires_at"]) if item.get("expires_at") else None
            if kind == "backups":
                for root, days in item.get("source_backup_grace_days", {}).items():
                    if root in disposed:
                        candidate = disposed[root] + timedelta(days=days)
                        deadline = min(deadline, candidate) if deadline else candidate
            item["expires_at"] = deadline.isoformat() if deadline else None
            item["expired"] = bool(deadline and deadline <= timestamp)
            item["present"] = _file_path(lifecycle, kind, item).is_file()
            item["usable"] = bool(item["present"] and not item["expired"] and not item["restricted_sources"])
            copies.append(item)
        result[kind] = copies
    result["unmanaged_copy_filenames"] = {
        kind: sorted(path.name for path in (lifecycle.store.db_path.parent / kind).glob("*")
                     if path.is_file() and not path.name.startswith(".") and
                     path.name not in {item["filename"] for item in result[kind]})
        for kind in ("exports", "backups")}
    return result


def managed_export(lifecycle, payload):
    directory = lifecycle.store.db_path.parent / "exports"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    identifier = str(uuid4())
    path = directory / f"twin-lab-export-{identifier}.json"
    with lifecycle.store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        responses = payload["responses"]
        for response in responses:
            if not lifecycle.normal_use(db, response["response_id"]):
                raise Conflict("A response became restricted. Refresh before exporting.")
        metadata = {lifecycle.metadata(db, item["response_id"])["root_response_id"]:
                    lifecycle.metadata(db, item["response_id"]) for item in responses}
        created = lifecycle.clock()
        deadlines = []
        for item in metadata.values():
            if item["expires_at"]:
                deadlines.extend((instant(item["expires_at"]), instant(created) +
                                  timedelta(days=item["policy"]["export_days"])))
        manifest = {"export_id": identifier, "created_at": created, "filename": path.name,
                    "source_root_ids": sorted(metadata), "response_ids": [row["response_id"] for row in responses],
                    "expires_at": min(deadlines).isoformat() if deadlines else None,
                    "copy_limitation": "Only this managed local copy is tracked. Downloaded or moved copies require custodian handling."}
        result = dict(payload, managed_export=manifest)
        encoded = canonical_json(result).encode("utf-8")
        manifest["sha256"] = hashlib.sha256(encoded).hexdigest()
        try:
            with path.open("xb") as output:
                path.chmod(0o600)
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            sync_directory(directory)
            db.execute("INSERT INTO managed_exports(id,payload) VALUES (?,?)", (identifier, canonical_json(manifest)))
        except BaseException:
            path.unlink(missing_ok=True)
            sync_directory(directory)
            raise
    # The hash covers the exact exported file, and stays in the inventory only.
    return json.loads(encoded), manifest


def plan_disposal(lifecycle, at=None, db=None):
    from .lifecycle_admin import administrative_review
    if db is None:
        with lifecycle.store.connection() as connection:
            connection.execute("BEGIN")
            return plan_disposal(lifecycle, at, connection)
    timestamp = at or lifecycle.clock()
    events = lifecycle.events(db)
    roots = {lifecycle.root_for(db, row[0])["response_id"] for row in db.execute("SELECT id FROM responses")}
    withdrawals = {event["withdrawal_id"]: event for event in events if event["kind"] == "withdrawal"}
    verified = {}
    for event in events:
        if event["kind"] == "verification":
            deadlines = dict(event["deadlines"])
            withdrawal = withdrawals.get(event["withdrawal_id"])
            if withdrawal is None:
                raise RuntimeError("Withdrawal verification has no matching receipt; recover the authoritative journals.")
            # A later restore can contain a chain absent during verification.
            # Its own frozen policy and the original verification time still bind;
            # restoring content never starts a fresh withdrawal clock.
            for root in withdrawal["root_ids"]:
                if root in deadlines or root not in roots:
                    continue
                metadata = lifecycle.metadata(db, root)
                days = metadata["policy"]["withdrawal_days"] if metadata["policy"] else event.get("withdrawal_days")
                if days is None:
                    continue  # Unknown legacy periods remain an explicit review gap.
                deadline = instant(event["verified_at"]) + timedelta(days=days)
                if metadata["expires_at"]:
                    deadline = min(deadline, instant(metadata["expires_at"]))
                deadlines[root] = deadline.isoformat()
            for root, deadline in deadlines.items():
                verified[root] = min(verified.get(root, deadline), deadline)
    eligible, held, unknown = [], [], []
    for root in roots:
        metadata = lifecycle.metadata(db, root)
        restriction = lifecycle.restriction(db, root, timestamp)
        if restriction == "legal_hold":
            held.append(root)
            continue
        deadlines = [instant(value) for value in (metadata["expires_at"], verified.get(root)) if value]
        if restriction == "disposal_recorded" or (deadlines and min(deadlines) <= instant(timestamp)):
            eligible.append(root)
        elif not deadlines:
            unknown.append(root)
    copies = inventory(lifecycle, db, timestamp)
    exports = [row["export_id"] for row in copies["exports"] if row["present"] and not row["held"] and
               (row["expired"] or set(row["source_root_ids"]) & set(eligible))]
    backups = [row["backup_id"] for row in copies["backups"] if row["present"] and not row["held"] and row["expired"]]
    plan = {"plan_schema_version": "1.0", "as_of": timestamp, "eligible_root_ids": sorted(eligible),
            "held_root_ids": sorted(held), "unknown_policy_root_ids": sorted(unknown),
            "export_ids": sorted(exports), "backup_ids": sorted(backups),
            "administrative_retention_review": administrative_review(lifecycle, db, timestamp),
            "unmanaged_copy_filenames": copies["unmanaged_copy_filenames"]}
    plan["confirmation"] = hashlib.sha256(canonical_json(plan).encode("utf-8")).hexdigest()
    return plan


def apply_disposal(lifecycle, plan, actor_code):
    from .lifecycle_restore import purge_roots
    actor = validate_code(actor_code)
    if not isinstance(plan, dict) or "confirmation" not in plan:
        raise ValidationError("Use an explicit, previously reviewed disposal plan.")
    if instant(plan["as_of"]) > instant(lifecycle.clock()):
        raise ValidationError("A future disposal plan cannot be applied.")
    with lifecycle.store.connection() as db:
        db.execute("PRAGMA secure_delete=ON")
        db.execute("BEGIN IMMEDIATE")
        expected = plan_disposal(lifecycle, plan["as_of"], db)
        if plan != expected:
            raise Conflict("Lifecycle state changed; review a new disposal plan.")
        roots = plan["eligible_root_ids"]
        if roots or plan["export_ids"] or plan["backup_ids"]:
            append_ledger(lifecycle.ledger_path, {"entry_id": str(uuid4()), "root_ids": roots,
                "deleted_at": lifecycle.clock(), "actor_code": actor,
                "plan_confirmation": plan["confirmation"], "status": "authorized",
                "export_ids": plan["export_ids"], "backup_ids": plan["backup_ids"]})
        if roots:
            purge_roots(db, set(roots))
        copies = inventory(lifecycle, db)
        removed = []
        for kind, identifier in (("exports", "export_id"), ("backups", "backup_id")):
            for manifest in copies[kind]:
                if manifest[identifier] in plan["export_ids" if kind == "exports" else "backup_ids"]:
                    path = _file_path(lifecycle, kind, manifest)
                    path.unlink(missing_ok=True)
                    sync_directory(path.parent)
                    removed.append(manifest[identifier])
        return {"disposed_root_ids": roots, "removed_copy_ids": removed,
                "forensic_erasure_claimed": False}


def restore_snapshot(source, destination, ledger_path):
    from .lifecycle_restore import restore_snapshot as restore
    return restore(source, destination, ledger_path)

"""Versioned collection planning. All capture remains synthetic demo capture."""

import json
from uuid import uuid4

from .backups import create_backup
from .collection_schema import GOVERNANCE_FIELDS, validate_assignment, validate_protocol
from .schemas import Conflict, NotFound, canonical_json, now, validate_code


class Collection:
    def __init__(self, store):
        self.store = store
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS collection_protocols (
                id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                request_body TEXT NOT NULL, payload TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS case_assignments (
                id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                protocol_id TEXT NOT NULL REFERENCES collection_protocols(id),
                physician_code TEXT NOT NULL, version_id TEXT NOT NULL REFERENCES case_versions(id),
                request_body TEXT NOT NULL, payload TEXT NOT NULL,
                UNIQUE(protocol_id, physician_code, version_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS local_backups (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL)""")
            for table in ("collection_protocols", "case_assignments", "local_backups"):
                for operation in ("UPDATE", "DELETE"):
                    db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{operation}
                        BEFORE {operation} ON {table} BEGIN
                        SELECT RAISE(ABORT, 'Append-only records'); END""")

    @staticmethod
    def _records(db, table):
        return [json.loads(row[0]) for row in db.execute(f"SELECT payload FROM {table} ORDER BY rowid")]

    @staticmethod
    def _retry(db, table, body):
        row = db.execute(f"SELECT request_body, payload FROM {table} WHERE request_id = ?",
                         (body["request_id"],)).fetchone()
        if row:
            if row[0] != canonical_json(body):
                raise Conflict("This request was already saved with different values. Refresh the history.")
            return json.loads(row[1])
        return None

    @staticmethod
    def _get(db, table, identifier):
        row = db.execute(f"SELECT payload FROM {table} WHERE id = ?", (identifier,)).fetchone()
        if not row:
            raise NotFound("The requested local planning record does not exist.")
        return json.loads(row[0])

    def overview(self):
        with self.store.connection() as db:
            db.execute("BEGIN")
            history = self._records(db, "collection_protocols")
            assignments = self._records(db, "case_assignments")
            backups = self._records(db, "local_backups")
            current = history[-1] if history else None
            missing = [key for key in GOVERNANCE_FIELDS if not current or
                       not (current[key].strip() if isinstance(current[key], str) else current[key])]
            current_assignments = [item for item in assignments
                                   if current and item["protocol_id"] == current["protocol_id"]]
            if not current_assignments:
                missing.append("case_assignments")
            unapproved = []
            for assignment in current_assignments:
                resolved = self.store.catalog.resolve(db, version_id=assignment["version_id"])
                if resolved["case_snapshot"]["review_status"] != "approved":
                    unapproved.append(assignment["assignment_id"])
        return {"current": current, "history": history, "assignments": assignments,
                "backups": backups,
                "readiness": {"missing_fields": missing, "unapproved_assignment_ids": unapproved,
                              "configuration_complete": not missing and not unapproved,
                              "study_collection_enabled": False}}

    def save_protocol(self, body):
        validate_protocol(body)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = self._retry(db, "collection_protocols", body)
            if existing:
                return existing, True
            history = self._records(db, "collection_protocols")
            latest = history[-1]["protocol_id"] if history else None
            if latest != body["based_on_protocol_id"]:
                raise Conflict("The collection plan changed. Refresh before recording a revision.")
            protocol = json.loads(canonical_json(body))
            protocol.update({"protocol_id": str(uuid4()), "created_at": now(),
                             "protocol_schema_version": "1.0", "collection_purpose": "demo",
                             "study_collection_enabled": False,
                             "assignment_strategy": "manual_version_pinned",
                             "physician_code_rule": "1–40 ASCII letters, digits, underscores or hyphens; case-sensitive"})
            for key in ("owner_code", "backup_owner_code"):
                protocol[key] = validate_code(body[key], required=False)
            protocol["physician_codes"] = [validate_code(code) for code in body["physician_codes"]]
            db.execute("INSERT INTO collection_protocols(id, request_id, request_body, payload) VALUES (?, ?, ?, ?)",
                       (protocol["protocol_id"], body["request_id"], canonical_json(body), canonical_json(protocol)))
        return protocol, False

    def assign(self, body):
        validate_assignment(body)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = self._retry(db, "case_assignments", body)
            if existing:
                return existing, True
            protocol = self._get(db, "collection_protocols", body["protocol_id"])
            latest = self._records(db, "collection_protocols")[-1]
            if latest["protocol_id"] != protocol["protocol_id"]:
                raise Conflict("Assignments must use the latest collection plan. Refresh the plan.")
            code = validate_code(body["physician_code"])
            if code not in protocol["physician_codes"]:
                raise Conflict("This physician code is not listed in the selected collection plan.")
            self.store.catalog.resolve(db, version_id=body["version_id"])
            if db.execute("SELECT 1 FROM case_assignments WHERE protocol_id = ? AND physician_code = ? AND version_id = ?",
                          (protocol["protocol_id"], code, body["version_id"])).fetchone():
                raise Conflict("This exact case version is already assigned to this code in this plan.")
            assignment = dict(body, assignment_id=str(uuid4()), created_at=now(), physician_code=code)
            db.execute("""INSERT INTO case_assignments
                (id, request_id, protocol_id, physician_code, version_id, request_body, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (assignment["assignment_id"], body["request_id"], protocol["protocol_id"], code,
                 body["version_id"], canonical_json(body), canonical_json(assignment)))
        return assignment, False

    def resolve_assignment(self, db, assignment_id):
        assignment = self._get(db, "case_assignments", assignment_id)
        resolved = self.store.catalog.resolve(db, version_id=assignment["version_id"])
        return dict(resolved, assignment_id=assignment_id, protocol_id=assignment["protocol_id"],
                    assigned_physician_code=assignment["physician_code"])

    def backup(self, body):
        return create_backup(self.store, body)

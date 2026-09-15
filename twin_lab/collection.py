"""Versioned collection planning. All capture remains synthetic demo capture."""

import json
from uuid import uuid4

from .backups import create_backup
from .collection_schema import (
    GOVERNANCE_FIELDS,
    PLANNING_FIELDS,
    validate_assignment,
    validate_protocol,
)
from .governance_schema import missing_fields
from .persistence import find_retry, get_record, read_records
from .schemas import Conflict, canonical_json, now, validate_code

MISSING_RECORD = "The requested local planning record does not exist."


class Collection:
    def __init__(self, store):
        self.store = store

    def overview(self):
        with self.store.connection() as db:
            db.execute("BEGIN")
            history = read_records(db, "collection_protocols")
            assignments = read_records(db, "case_assignments")
            backups = read_records(db, "local_backups")
            current = history[-1] if history else None
            linked = current is not None and current["protocol_schema_version"] == "2.0"
            governance = self.store.governance._current(db)
            missing = [
                key
                for key in (PLANNING_FIELDS if linked else GOVERNANCE_FIELDS)
                if not current
                or not (current[key].strip() if isinstance(current[key], str) else current[key])
            ]
            pin_current = None
            if linked and current is not None:
                pinned = self.store.governance.get(db, current["governance_id"])
                pin_current = bool(
                    governance and current["governance_id"] == governance["governance_id"]
                )
                if not pin_current:
                    missing.append("stale_governance")
                missing.extend(f"governance.{field}" for field in missing_fields(pinned))
            elif governance and governance.get("governance_schema_version") == "2.0":
                pin_current = False
                missing.append("linked_plan")
            current_assignments = [
                item
                for item in assignments
                if current and item["protocol_id"] == current["protocol_id"]
            ]
            if not current_assignments:
                missing.append("case_assignments")
            unapproved = []
            for assignment in current_assignments:
                resolved = self.store.catalog.resolve(db, version_id=assignment["version_id"])
                if resolved["case_snapshot"]["review_status"] != "approved":
                    unapproved.append(assignment["assignment_id"])
        return {
            "current": current,
            "history": history,
            "assignments": assignments,
            "backups": backups,
            "readiness": {
                "missing_fields": missing,
                "unapproved_assignment_ids": unapproved,
                "configuration_complete": not missing and not unapproved,
                "study_collection_enabled": False,
                "governance_pin_current": pin_current,
            },
        }

    def save_protocol(self, body):
        validate_protocol(body)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = find_retry(
                db, "collection_protocols", body["request_id"], canonical_json(body)
            )
            if existing:
                return existing, True
            history = read_records(db, "collection_protocols")
            latest = history[-1]["protocol_id"] if history else None
            if latest != body["based_on_protocol_id"]:
                raise Conflict("The collection plan changed. Refresh before recording a revision.")
            v2 = body.get("protocol_schema_version") == "2.0"
            if history and history[-1]["protocol_schema_version"] == "2.0" and not v2:
                raise Conflict(
                    "The current plan uses v2; save a version 2 revision and preserve its governance pin."
                )
            if v2:
                self.store.governance.get(db, body["governance_id"])
            protocol = json.loads(canonical_json(body))
            protocol.update(
                {
                    "protocol_id": str(uuid4()),
                    "created_at": now(),
                    "protocol_schema_version": "2.0" if v2 else "1.0",
                    "collection_purpose": "demo",
                    "study_collection_enabled": False,
                    "assignment_strategy": "manual_version_pinned",
                    "physician_code_rule": "1–40 ASCII letters, digits, underscores or hyphens; case-sensitive",
                }
            )
            for key in ("owner_code", "backup_owner_code"):
                protocol[key] = validate_code(body[key], required=False)
            protocol["physician_codes"] = [validate_code(code) for code in body["physician_codes"]]
            db.execute(
                "INSERT INTO collection_protocols(id, request_id, request_body, payload) VALUES (?, ?, ?, ?)",
                (
                    protocol["protocol_id"],
                    body["request_id"],
                    canonical_json(body),
                    canonical_json(protocol),
                ),
            )
        return protocol, False

    def assign(self, body):
        validate_assignment(body)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = find_retry(db, "case_assignments", body["request_id"], canonical_json(body))
            if existing:
                return existing, True
            protocol = get_record(
                db, "collection_protocols", body["protocol_id"], missing=MISSING_RECORD
            )
            latest = read_records(db, "collection_protocols")[-1]
            if latest["protocol_id"] != protocol["protocol_id"]:
                raise Conflict("Assignments must use the latest collection plan. Refresh the plan.")
            code = validate_code(body["physician_code"])
            if code not in protocol["physician_codes"]:
                raise Conflict("This physician code is not listed in the selected collection plan.")
            self.store.catalog.resolve(db, version_id=body["version_id"])
            if db.execute(
                "SELECT 1 FROM case_assignments WHERE protocol_id = ? AND physician_code = ? AND version_id = ?",
                (protocol["protocol_id"], code, body["version_id"]),
            ).fetchone():
                raise Conflict(
                    "This exact case version is already assigned to this code in this plan."
                )
            self._require_assignment_room(db, protocol, code, body["version_id"])
            assignment = dict(
                body, assignment_id=str(uuid4()), created_at=now(), physician_code=code
            )
            db.execute(
                """INSERT INTO case_assignments
                (id, request_id, protocol_id, physician_code, version_id, request_body, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    assignment["assignment_id"],
                    body["request_id"],
                    protocol["protocol_id"],
                    code,
                    body["version_id"],
                    canonical_json(body),
                    canonical_json(assignment),
                ),
            )
        return assignment, False

    def _require_assignment_room(self, db, protocol, code, version_id):
        if protocol["protocol_schema_version"] != "2.0":
            return
        governance = self.store.governance.get(db, protocol["governance_id"])
        limit = (governance.get("session") or {}).get("max_distinct_case_versions")
        if limit is None:
            return  # Unknown draft/legacy scope grants no human permission.
        scope_plans = {
            item["protocol_id"]
            for item in read_records(db, "collection_protocols")
            if item.get("governance_id") == governance["governance_id"]
        }
        assigned = {
            item["version_id"]
            for item in read_records(db, "case_assignments")
            if item["protocol_id"] in scope_plans and item["physician_code"] == code
        }
        if version_id not in assigned and len(assigned) >= limit:
            raise Conflict(
                "This governance revision's distinct case-version limit is reached for this code. A plan revision does not reset it."
            )

    def resolve_assignment(self, db, assignment_id):
        assignment = get_record(db, "case_assignments", assignment_id, missing=MISSING_RECORD)
        resolved = self.store.catalog.resolve(db, version_id=assignment["version_id"])
        return dict(
            resolved,
            assignment_id=assignment_id,
            protocol_id=assignment["protocol_id"],
            assigned_physician_code=assignment["physician_code"],
        )

    def backup(self, body):
        return create_backup(self.store, body)

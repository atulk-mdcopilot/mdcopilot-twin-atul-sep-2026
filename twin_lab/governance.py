"""Versioned permission and local human-demo gates, separate from study consent."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .governance_schema import missing_fields, validate_governance, validate_permission
from .persistence import find_retry, get_record, read_records
from .schemas import Conflict, ValidationError, canonical_json, now, validate_code, validate_id

DOCUMENTS = Path(__file__).resolve().parent.parent / "docs" / "governance"
MISSING_RECORD = "The requested local planning record does not exist."
DOCUMENT_FILES = {
    "json": ("twin-governance.example.json", "application/json; charset=utf-8"),
    "markdown": ("governance-samples-v0.1.md", "text/markdown; charset=utf-8"),
}


def reference_documents():
    """Source document approval is distinct from the private operating record."""
    policy = json.loads((DOCUMENTS / DOCUMENT_FILES["json"][0]).read_text(encoding="utf-8"))
    return {
        "policy": policy,
        "files": [
            {
                "format": kind,
                "filename": name,
                "url": f"/api/governance-documents/{kind}",
                "sha256": hashlib.sha256((DOCUMENTS / name).read_bytes()).hexdigest(),
            }
            for kind, (name, _) in DOCUMENT_FILES.items()
        ],
    }


class Governance:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def get(db, governance_id):
        validate_id(governance_id)
        return get_record(db, "governance_versions", governance_id, missing=MISSING_RECORD)

    @staticmethod
    def _current(db):
        row = db.execute(
            "SELECT payload FROM governance_versions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def _restore_requires_approval(db, current):
        row = db.execute(
            "SELECT payload FROM restore_barriers ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if not row:
            return False
        if current is None:
            return True
        try:
            restored_at = datetime.fromisoformat(json.loads(row[0])["restored_at"])
            approved_at = datetime.fromisoformat(current["created_at"])
            if restored_at.tzinfo is None or approved_at.tzinfo is None:
                raise ValueError
            return approved_at <= restored_at
        except (KeyError, ValueError, TypeError) as exc:
            raise RuntimeError(
                "Restore barrier is invalid; actual physician capture is disabled."
            ) from exc

    def overview(self):
        with self.store.connection() as db:
            db.execute("BEGIN")
            history = read_records(db, "governance_versions")
            receipts = read_records(db, "permission_receipts")
            current = history[-1] if history else None
            missing = missing_fields(current)
            if self._restore_requires_approval(db, current):
                missing.append("restore_reapproval_required")
        return {
            "current": current,
            "history": history,
            "receipts": receipts,
            "reference_documents": reference_documents(),
            "readiness": {
                "missing_fields": missing,
                "actual_physician_capture_enabled": not missing,
                "study_collection_enabled": False,
            },
        }

    def save(self, body):
        validate_governance(body)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = find_retry(
                db, "governance_versions", body["request_id"], canonical_json(body)
            )
            if existing:
                return existing, True
            current = self._current(db)
            if (current["governance_id"] if current else None) != body["based_on_governance_id"]:
                raise Conflict("Governance changed. Refresh before saving a revision.")
            if (
                current
                and current.get("governance_schema_version") == "2.0"
                and body.get("governance_schema_version") != "2.0"
            ):
                raise Conflict(
                    "Governance now uses v2; save a version 2 revision without removing its pilot scope."
                )
            if body["status"] == "approved" and missing_fields(
                body, include_status=False, include_window=False
            ):
                raise ValidationError(
                    "Approval requires completed operator, accepted owners, permission, retention, review and controls fields."
                )
            if body["status"] == "approved":
                for previous in read_records(db, "governance_versions"):
                    if (
                        previous["status"] == "approved"
                        and previous["permission"]["version"] == body["permission"]["version"]
                        and (
                            previous["permission"]["text"] != body["permission"]["text"]
                            or body.get("governance_schema_version") == "2.0"
                        )
                    ):
                        raise Conflict(
                            "Changed permission text and every new approved v2 scope require a new document version."
                        )
            if body["status"] == "revoked" and (
                not body["approved_by_code"].strip() or not body["approval_note"].strip()
            ):
                raise ValidationError("Record the actor code and reason for revocation.")
            record = json.loads(canonical_json(body))
            record.update(
                {
                    "governance_id": str(uuid4()),
                    "created_at": now(),
                    "governance_schema_version": body.get("governance_schema_version", "1.0"),
                    "collection_purpose": "demo",
                    "study_collection_enabled": False,
                    "training_allowed": False,
                    "research_reuse_allowed": False,
                    "public_release_allowed": False,
                    "permission_sha256": hashlib.sha256(
                        body["permission"]["text"].encode("utf-8")
                    ).hexdigest(),
                }
            )
            db.execute(
                "INSERT INTO governance_versions VALUES (?, ?, ?, ?)",
                (
                    record["governance_id"],
                    body["request_id"],
                    canonical_json(body),
                    canonical_json(record),
                ),
            )
        return record, False

    def _require_current(self, db, governance_id=None):
        current = self._current(db)
        if self._restore_requires_approval(db, current):
            raise Conflict(
                "This database was restored. Record fresh governance approval and new participant permission before actual physician capture."
            )
        if missing_fields(current):
            raise Conflict(
                "Actual physician capture requires current approved, complete demo governance and control attestations."
            )
        if governance_id is not None and current["governance_id"] != governance_id:
            raise Conflict(
                "Permission refers to an earlier governance version. Review the current notice and record a new choice."
            )
        return current

    @staticmethod
    def _current_protocol(db, code, governance):
        row = db.execute(
            "SELECT payload FROM collection_protocols ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        protocol = json.loads(row[0]) if row else None
        if not protocol or code not in protocol["physician_codes"]:
            raise Conflict("This participant code must be listed in the current collection plan.")
        if protocol["protocol_schema_version"] == "2.0":
            if protocol["governance_id"] != governance["governance_id"]:
                raise Conflict(
                    "The linked plan refers to an earlier governance revision. Save an explicitly linked current plan."
                )
        elif governance.get("governance_schema_version") == "2.0":
            raise Conflict(
                "This v2 governance scope requires a linked v2 collection plan before participant permission or capture."
            )
        return protocol

    def _require_not_withdrawn(self, db, code, receipt_id=None):
        lifecycle = getattr(self.store, "lifecycle", None)
        if lifecycle is None:
            raise Conflict(
                "Lifecycle controls are unavailable; actual physician capture is disabled."
            )
        if lifecycle.is_blocked(db, code, receipt_id):
            raise Conflict("Capture is stopped because this participant has a withdrawal record.")

    def permission(self, body):
        validate_permission(body)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = find_retry(
                db, "permission_receipts", body["request_id"], canonical_json(body)
            )
            if existing:
                if existing["permission_schema_version"] == "2.0":
                    current = self._require_current(db, existing["governance_id"])
                    self._current_protocol(db, existing["physician_code"], current)
                    self._require_not_withdrawn(
                        db, existing["physician_code"], existing["receipt_id"]
                    )
                return existing, True
            current = self._require_current(db, body["governance_id"])
            code = validate_code(body["physician_code"])
            self._current_protocol(db, code, current)
            self._require_not_withdrawn(db, code)
            receipt = dict(
                body,
                physician_code=code,
                receipt_id=str(uuid4()),
                recorded_at=now(),
                permission_version=current["permission"]["version"],
                permission_text=current["permission"]["text"],
                permission_sha256=current["permission_sha256"],
                collection_purpose="demo",
                permission_schema_version="1.0",
                research_reuse_allowed=False,
                training_allowed=False,
                public_release_allowed=False,
            )
            if current.get("governance_schema_version") == "2.0":
                receipt.update(
                    permission_schema_version="2.0",
                    session=current["session"],
                    professional_role=current["operator"]["professional_role"],
                    pilot_window={
                        key: current["operator"][key]
                        for key in ("pilot_start_date", "pilot_close_date")
                    },
                )
            db.execute(
                "INSERT INTO permission_receipts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    receipt["receipt_id"],
                    body["request_id"],
                    body["governance_id"],
                    code,
                    canonical_json(body),
                    canonical_json(receipt),
                ),
            )
        return receipt, False

    def receipt(self, receipt_id):
        validate_id(receipt_id)
        with self.store.connection() as db:
            return get_record(db, "permission_receipts", receipt_id, missing=MISSING_RECORD)

    def authorize(
        self,
        db,
        mode,
        receipt_id=None,
        code=None,
        assignment_id=None,
        protocol_id=None,
        version_id=None,
    ):
        if mode not in ("fabricated_qa", "physician_demo"):
            raise ValidationError("Choose fabricated QA or actual physician demo capture.")
        metadata = {
            "capture_mode": mode,
            "governance_id": None,
            "permission_receipt_id": None,
            "permission_version": None,
            "permission_sha256": None,
            "training_allowed": False,
            "research_reuse_allowed": False,
            "public_release_allowed": False,
        }
        if mode == "fabricated_qa":
            if receipt_id is not None:
                raise ValidationError(
                    "Fabricated QA cannot be represented as participant permission."
                )
            return metadata
        validate_id(receipt_id)
        receipt = get_record(db, "permission_receipts", receipt_id, missing=MISSING_RECORD)
        current = self._require_current(db, receipt["governance_id"])
        participant = receipt["physician_code"]
        if code is not None and validate_code(code) != participant:
            raise Conflict("The response code must match the participant permission receipt.")
        latest = db.execute(
            "SELECT id FROM permission_receipts WHERE physician_code = ? ORDER BY rowid DESC LIMIT 1",
            (participant,),
        ).fetchone()
        if receipt["choice"] != "agree" or not latest or latest[0] != receipt_id:
            raise Conflict(
                "Actual physician capture requires the participant's latest choice to be Agree."
            )
        self._require_not_withdrawn(db, participant, receipt_id)
        current_protocol = self._current_protocol(db, participant, current)
        if assignment_id is None:
            raise Conflict("Actual physician capture requires a pinned assignment.")
        validate_id(assignment_id)
        assignment = get_record(db, "case_assignments", assignment_id, missing=MISSING_RECORD)
        if (
            assignment["physician_code"] != participant
            or assignment["protocol_id"] != current_protocol["protocol_id"]
            or (protocol_id is not None and assignment["protocol_id"] != protocol_id)
            or (version_id is not None and assignment["version_id"] != version_id)
        ):
            raise Conflict(
                "The assignment must match the current plan, exact case version and permission code."
            )
        resolved = self.store.catalog.resolve(db, version_id=assignment["version_id"])
        if resolved["case_snapshot"]["review_status"] != "approved":
            raise Conflict(
                "Actual physician capture requires approval of this exact assigned case version."
            )
        metadata.update(
            {
                "governance_id": current["governance_id"],
                "permission_receipt_id": receipt_id,
                "permission_version": receipt["permission_version"],
                "permission_sha256": receipt["permission_sha256"],
            }
        )
        return metadata

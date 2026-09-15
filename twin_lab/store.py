"""Local transactional capture; authorized offline lifecycle disposal is separate."""

import json
from pathlib import Path
from uuid import uuid4

from .catalog import Catalog
from .collection import Collection
from .governance import Governance
from .lifecycle import Lifecycle
from .migrations import initialize
from .persistence import connection, get_record, read_records
from .schemas import (
    SCHEMA_VERSION,
    Conflict,
    ValidationError,
    canonical_json,
    now,
    read_json,
    snapshot_hash,
    validate_case,
    validate_id,
    validate_values,
)
from .schemas import NotFound as NotFound

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cases.json"


PRESENTATION_REFS = ("case_version_id", "case_review_id", "assignment_id", "protocol_id")
GOVERNANCE_REFS = (
    "capture_mode",
    "governance_id",
    "permission_receipt_id",
    "permission_version",
    "permission_sha256",
)


class Store:
    def __init__(self, db_path, fixtures_path=FIXTURES):
        self.db_path = Path(db_path)
        cases = read_json(Path(fixtures_path).read_text(encoding="utf-8"))
        if not isinstance(cases, list) or len(cases) != 5:
            raise ValidationError("Twin Lab v0.1 requires exactly five synthetic demo fixtures.")
        for case in cases:
            validate_case(case)
        if len({case["case_id"] for case in cases}) != 5:
            raise ValidationError("Case identifiers must be unique.")
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.catalog = Catalog(self.connection)
        self.collection = Collection(self)
        self.governance = Governance(self)
        self.lifecycle = Lifecycle(self)
        initialize(
            self, cases, include_families=Path(fixtures_path).resolve() == FIXTURES.resolve()
        )
        self.db_path.chmod(0o600)

    def connection(self):
        return connection(self.db_path)

    def cases(self):
        return self.catalog.cases()

    @staticmethod
    def _require_latest(db, identifier):
        if db.execute("SELECT 1 FROM responses WHERE supersedes_id = ?", (identifier,)).fetchone():
            raise Conflict(
                "This response already has a correction. Review and correct the latest revision."
            )

    def present(
        self,
        case_id=None,
        supersedes_response_id=None,
        version_id=None,
        assignment_id=None,
        capture_mode=None,
        permission_receipt_id=None,
        qa_acknowledged=False,
    ):
        if (
            sum(
                value is not None
                for value in (case_id, supersedes_response_id, version_id, assignment_id)
            )
            != 1
        ):
            raise ValidationError(
                "Choose one case, exact version, assignment, or response to correct."
            )
        if type(qa_acknowledged) is not bool:
            raise ValidationError("The fabricated-answer acknowledgment must be true or false.")
        if capture_mode == "fabricated_qa" and not qa_acknowledged:
            raise ValidationError(
                "Confirm that these are fabricated software-test answers before opening the case."
            )
        if capture_mode != "fabricated_qa" and qa_acknowledged:
            raise ValidationError(
                "The fabricated-answer acknowledgment does not apply to this mode."
            )
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = None
            if supersedes_response_id is not None:
                validate_id(supersedes_response_id)
                previous = get_record(db, "responses", supersedes_response_id)
                if not self.lifecycle.normal_use(db, supersedes_response_id):
                    raise Conflict("This response is restricted by its lifecycle status.")
                self._require_latest(db, supersedes_response_id)
                previous_mode = previous.get("capture_mode", "legacy_unclassified")
                if capture_mode != previous_mode or permission_receipt_id != previous.get(
                    "permission_receipt_id"
                ):
                    raise Conflict(
                        "A correction must preserve the original capture mode and permission reference."
                    )
                resolved = {
                    "case_snapshot": previous["case_snapshot"],
                    **{key: previous.get(key) for key in PRESENTATION_REFS},
                }
                if previous.get("assignment_id"):
                    resolved["assigned_physician_code"] = previous["physician_code"]
            elif assignment_id is not None:
                validate_id(assignment_id)
                resolved = self.collection.resolve_assignment(db, assignment_id)
            else:
                resolved = self.catalog.resolve(db, case_id=case_id, version_id=version_id)
            if capture_mode == "legacy_unclassified" and previous is not None:
                governance = {
                    "capture_mode": "legacy_unclassified",
                    "governance_id": None,
                    "permission_receipt_id": None,
                    "permission_version": None,
                    "permission_sha256": None,
                }
                self.lifecycle.require_capture(db, previous["physician_code"])
            else:
                governance = self.governance.authorize(
                    db,
                    capture_mode,
                    permission_receipt_id,
                    code=previous["physician_code"]
                    if previous
                    else resolved.get("assigned_physician_code"),
                    assignment_id=resolved.get("assignment_id"),
                    protocol_id=resolved.get("protocol_id"),
                    version_id=resolved.get("case_version_id"),
                )
            snapshot = resolved["case_snapshot"]
            presentation = {
                "presentation_id": str(uuid4()),
                "presented_at": now(),
                "case_snapshot": snapshot,
                "snapshot_sha256": snapshot_hash(snapshot),
                "supersedes_response_id": supersedes_response_id,
                **{key: resolved.get(key) for key in PRESENTATION_REFS},
                "assigned_physician_code": resolved.get("assigned_physician_code"),
                **{key: governance.get(key) for key in GOVERNANCE_REFS},
                "qa_acknowledged": qa_acknowledged,
            }
            payload = canonical_json(presentation)
            db.execute(
                "INSERT INTO presentations(id, payload) VALUES (?, ?)",
                (presentation["presentation_id"], payload),
            )
        return json.loads(payload)

    def submit(self, presentation_id, values):
        validate_id(presentation_id)
        validate_values(values)
        # Round trip freezes the supplied values before transactional comparison.
        original = json.loads(canonical_json(values))
        normalized = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in original.items()
        }
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT payload FROM responses WHERE presentation_id = ?", (presentation_id,)
            ).fetchone()
            if existing:
                response = json.loads(existing[0])
                if not self.lifecycle.normal_use(db, response["response_id"]):
                    raise Conflict("This saved response is restricted by its lifecycle status.")
                if response["original_values"] != original:
                    raise Conflict(
                        "This presentation was already saved. Review it and use an explicit correction."
                    )
                if response.get("capture_mode") == "physician_demo":
                    self.governance.authorize(
                        db,
                        "physician_demo",
                        response["permission_receipt_id"],
                        code=response["physician_code"],
                        assignment_id=response["assignment_id"],
                        protocol_id=response["protocol_id"],
                        version_id=response["case_version_id"],
                    )
                return response, True
            presentation = get_record(db, "presentations", presentation_id)
            mode = presentation.get("capture_mode")
            if mode is None:
                raise Conflict(
                    "This case was opened before the governance update. Reopen it and choose the capture mode."
                )
            self.lifecycle.require_capture(
                db, normalized["physician_code"], presentation.get("permission_receipt_id")
            )
            assigned_code = presentation.get("assigned_physician_code")
            if assigned_code and assigned_code != normalized["physician_code"]:
                raise Conflict("This assignment requires its planned physician code.")
            supersedes = presentation["supersedes_response_id"]
            if supersedes is not None:
                previous = get_record(db, "responses", supersedes)
                if not self.lifecycle.normal_use(db, supersedes):
                    raise Conflict("This response is restricted by its lifecycle status.")
                self._require_latest(db, supersedes)
                if previous["physician_code"] != normalized["physician_code"]:
                    raise Conflict("A correction must retain the original physician code.")
            if mode != "legacy_unclassified":
                verified = self.governance.authorize(
                    db,
                    mode,
                    presentation.get("permission_receipt_id"),
                    code=normalized["physician_code"],
                    assignment_id=presentation.get("assignment_id"),
                    protocol_id=presentation.get("protocol_id"),
                    version_id=presentation.get("case_version_id"),
                )
                if any(verified.get(key) != presentation.get(key) for key in GOVERNANCE_REFS):
                    raise Conflict(
                        "Permission changed after this case was opened. Reopen the case."
                    )
            elif supersedes is None:
                raise Conflict(
                    "Unclassified status is reserved for corrections of historical responses."
                )
            case = presentation["case_snapshot"]
            response = {
                "response_id": str(uuid4()),
                "presentation_id": presentation_id,
                "physician_code": normalized["physician_code"],
                "case_id": case["case_id"],
                "case_family": case["family_id"],
                "case_version": case["version"],
                "response_schema_version": SCHEMA_VERSION,
                "case_snapshot": case,
                "snapshot_sha256": presentation["snapshot_sha256"],
                "presented_at": presentation["presented_at"],
                "submitted_at": now(),
                "original_values": original,
                "normalized_values": normalized,
                "ai_advice_shown": False,
                "collection_purpose": case["collection_purpose"],
                "case_review_status": case["review_status"],
                "eligible_for_study": False,
                "supersedes_response_id": supersedes,
                **{key: presentation.get(key) for key in PRESENTATION_REFS},
                **{key: presentation.get(key) for key in GOVERNANCE_REFS},
                "training_allowed": False,
                "research_reuse_allowed": False,
                "public_release_allowed": False,
            }
            payload = canonical_json(response)
            db.execute(
                "INSERT INTO responses(id, presentation_id, supersedes_id, payload) VALUES (?, ?, ?, ?)",
                (response["response_id"], presentation_id, supersedes, payload),
            )
            governance_record = (
                self.governance.get(db, response["governance_id"])
                if response["governance_id"]
                else None
            )
            self.lifecycle.attach(
                db, response, governance_record, response["permission_receipt_id"]
            )
        return json.loads(payload), False

    def responses(self):
        with self.connection() as db:
            db.execute("BEGIN")
            return [
                json.loads(row[0])
                for row in db.execute("SELECT payload FROM responses ORDER BY rowid")
                if self.lifecycle.normal_use(db, json.loads(row[0])["response_id"])
            ]

    def export(self):
        # A single read transaction gives responses and every referenced record
        # one consistent point in time, even while another tab saves a revision.
        with self.connection() as db:
            db.execute("BEGIN")
            tables = {
                table: read_records(db, table)
                for table in (
                    "responses",
                    "case_versions",
                    "case_reviews",
                    "case_families",
                    "collection_protocols",
                    "case_assignments",
                )
            }
            tables["responses"] = [
                item
                for item in tables["responses"]
                if self.lifecycle.normal_use(db, item["response_id"])
            ]
        latest_reviews = {item["version_id"]: item for item in tables["case_reviews"]}
        for version in tables["case_versions"]:
            version["latest_review"] = latest_reviews.get(version["version_id"])
        responses = tables.pop("responses")
        tables["assignments"] = tables.pop("case_assignments")
        return {
            "export_schema_version": SCHEMA_VERSION,
            "exported_at": now(),
            "application": "Twin Lab v0.1",
            "synthetic_only": True,
            "response_count": len(responses),
            "responses": responses,
            **tables,
        }

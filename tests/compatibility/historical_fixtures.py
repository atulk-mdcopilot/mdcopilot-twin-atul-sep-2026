"""Independent v1/v2 SQLite layouts and fabricated historical observations.

These schemas intentionally do not import the production migration coordinator.
Noncanonical payload whitespace and Unicode catch accidental JSON rewriting.
"""

import copy
import hashlib
import json
import sqlite3
from uuid import NAMESPACE_URL, uuid5

from helpers import FIXTURES, values

CORE_DDL = (
    "CREATE TABLE presentations (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    """CREATE TABLE responses (id TEXT PRIMARY KEY,
        presentation_id TEXT NOT NULL UNIQUE REFERENCES presentations(id),
        supersedes_id TEXT UNIQUE REFERENCES responses(id), payload TEXT NOT NULL)""",
)
V2_DDL = (
    """CREATE TABLE case_versions (id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
        version_label TEXT NOT NULL, based_on_id TEXT UNIQUE REFERENCES case_versions(id),
        request_id TEXT UNIQUE, request_body TEXT, payload TEXT NOT NULL,
        UNIQUE(case_id, version_label))""",
    """CREATE TABLE case_reviews (id TEXT PRIMARY KEY,
        version_id TEXT NOT NULL REFERENCES case_versions(id),
        supersedes_id TEXT UNIQUE REFERENCES case_reviews(id),
        request_id TEXT NOT NULL UNIQUE, request_body TEXT NOT NULL, payload TEXT NOT NULL)""",
    "CREATE TABLE case_families (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    """CREATE TABLE collection_protocols (id TEXT PRIMARY KEY,
        request_id TEXT UNIQUE NOT NULL, request_body TEXT NOT NULL, payload TEXT NOT NULL)""",
    """CREATE TABLE case_assignments (id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
        protocol_id TEXT NOT NULL REFERENCES collection_protocols(id),
        physician_code TEXT NOT NULL, version_id TEXT NOT NULL REFERENCES case_versions(id),
        request_body TEXT NOT NULL, payload TEXT NOT NULL,
        UNIQUE(protocol_id, physician_code, version_id))""",
    "CREATE TABLE local_backups (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
)
STAMP = "2026-09-08T12:00:00.000000+00:00"


def identifier(label):
    return str(uuid5(NAMESPACE_URL, "twin-compatibility/" + label))


def frozen_json(value):
    return json.dumps(value, ensure_ascii=False, indent=3) + "\n"


def request_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def historical_database(path, version):
    """Create only tables available in the named historical database version."""
    snapshot = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
    with sqlite3.connect(path) as db:
        for statement in CORE_DDL + (V2_DDL if version == 2 else ()):
            db.execute(statement)
        refs, requests = ({}, {}) if version == 1 else _v2_records(db, snapshot)
        if version == 2:
            snapshot["review_status"] = "approved"
        digest = hashlib.sha256(request_json(snapshot).encode("utf-8")).hexdigest()
        responses = []
        for index in range(2):
            presentation_id = identifier(f"v{version}-presentation-{index}")
            prior = responses[-1]["response_id"] if responses else None
            presentation = {
                "presentation_id": presentation_id,
                "presented_at": STAMP,
                "case_snapshot": snapshot,
                "snapshot_sha256": digest,
                "supersedes_response_id": prior,
                **refs,
            }
            original = values(
                next_action=f"  Fabricated historical answer {index}.  ",
                rationale='  Café, "quoted" text.\nSecond line.  ',
            )
            response = {
                "response_id": identifier(f"v{version}-response-{index}"),
                "presentation_id": presentation_id,
                "physician_code": "DEMO_01",
                "case_id": snapshot["case_id"],
                "case_family": snapshot["family_id"],
                "case_version": snapshot["version"],
                "response_schema_version": "1.0" if version == 1 else "1.1",
                "case_snapshot": snapshot,
                "snapshot_sha256": digest,
                "presented_at": STAMP,
                "submitted_at": STAMP,
                "original_values": original,
                "normalized_values": {
                    key: value.strip() if isinstance(value, str) else value
                    for key, value in original.items()
                },
                "ai_advice_shown": False,
                "collection_purpose": "demo",
                "case_review_status": snapshot["review_status"],
                "eligible_for_study": False,
                "supersedes_response_id": prior,
                **refs,
            }
            db.execute(
                "INSERT INTO presentations VALUES (?, ?)",
                (presentation_id, frozen_json(presentation)),
            )
            db.execute(
                "INSERT INTO responses VALUES (?, ?, ?, ?)",
                (response["response_id"], presentation_id, prior, frozen_json(response)),
            )
            responses.append(response)
        db.execute(f"PRAGMA user_version = {version}")
    return responses, requests


def _v2_records(db, snapshot):
    version_id = str(uuid5(NAMESPACE_URL, f"twin-lab/case/{snapshot['case_id']}/1.0"))
    version = {
        "version_id": version_id,
        "case_id": snapshot["case_id"],
        "case_version": "1.0",
        "snapshot": copy.deepcopy(snapshot),
        "snapshot_sha256": hashlib.sha256(request_json(snapshot).encode()).hexdigest(),
        "created_at": STAMP,
        "editor_code": None,
        "change_note": "Fabricated historical source fixture.",
        "based_on_version": None,
    }
    db.execute(
        "INSERT INTO case_versions VALUES (?, ?, ?, ?, ?, ?, ?)",
        (version_id, snapshot["case_id"], "1.0", None, None, None, frozen_json(version)),
    )
    review_body = {
        "request_id": identifier("review-request"),
        "version_id": version_id,
        "reviewer_code": "STF-TEST",
        "reviewed_on": "2026-09-08",
        "comments": "Fabricated review. Café.\n",
        "disposition": "approved",
        "supersedes_review_id": None,
    }
    review = dict(review_body, review_id=identifier("review"), recorded_at=STAMP)
    db.execute(
        "INSERT INTO case_reviews VALUES (?, ?, ?, ?, ?, ?)",
        (
            review["review_id"],
            version_id,
            None,
            review_body["request_id"],
            request_json(review_body),
            frozen_json(review),
        ),
    )
    plan_body = {
        "request_id": identifier("plan-request"),
        "based_on_protocol_id": None,
        "title": "Fabricated historical plan",
        "owner_code": "STF-TEST",
        "physician_codes": ["DEMO_01"],
        "consent_statement": "Historical draft only.\n",
        "consent_version": "TEST-DRAFT-1",
        "retention_days": None,
        "backup_owner_code": "",
        "backup_frequency": "manual_before_changes",
        "backup_retention_days": None,
        "notes": "Preserve original plan values. Café.",
    }
    plan = dict(
        plan_body,
        protocol_id=identifier("plan"),
        created_at=STAMP,
        protocol_schema_version="1.0",
        collection_purpose="demo",
        study_collection_enabled=False,
        assignment_strategy="manual_version_pinned",
        physician_code_rule="1–40 ASCII letters, digits, underscores or hyphens; case-sensitive",
    )
    db.execute(
        "INSERT INTO collection_protocols VALUES (?, ?, ?, ?)",
        (plan["protocol_id"], plan_body["request_id"], request_json(plan_body), frozen_json(plan)),
    )
    assignment_body = {
        "request_id": identifier("assignment-request"),
        "protocol_id": plan["protocol_id"],
        "physician_code": "DEMO_01",
        "version_id": version_id,
        "notes": "Exact historical version.",
    }
    assignment = dict(assignment_body, assignment_id=identifier("assignment"), created_at=STAMP)
    db.execute(
        "INSERT INTO case_assignments VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            assignment["assignment_id"],
            assignment_body["request_id"],
            plan["protocol_id"],
            "DEMO_01",
            version_id,
            request_json(assignment_body),
            frozen_json(assignment),
        ),
    )
    refs = {
        "case_version_id": version_id,
        "case_review_id": review["review_id"],
        "assignment_id": assignment["assignment_id"],
        "protocol_id": plan["protocol_id"],
    }
    requests = {
        "review": (review_body, review),
        "plan": (plan_body, plan),
        "assignment": (assignment_body, assignment),
    }
    return refs, requests


def raw_rows(path):
    """SQLite bytes, not parsed/reserialized JSON; fixed internal schema names only."""
    with sqlite3.connect(path) as db:
        tables = [
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ]
        db.text_factory = bytes
        return {
            table: db.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            for table in tables
        }

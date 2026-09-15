"""Synthetic-only test data; all databases live in TemporaryDirectory."""

from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "cases.json"


def qa_presentation(**selector):
    return dict(
        selector, capture_mode="fabricated_qa", permission_receipt_id=None, qa_acknowledged=True
    )


def latest_version(catalog, case_id=None):
    case_id = case_id or catalog["versions"][0]["case_id"]
    return next(
        version for version in reversed(catalog["versions"]) if version["case_id"] == case_id
    )


def values(**changes):
    result = {
        "physician_code": "  DEMO_01  ",
        "next_action": "  Insufficient information to decide yet.  ",
        "next_information": "  Request the observations available now.\n  ",
        "decision_change": "  A change in the available observations.  ",
        "rationale": "",
        "confidence": None,
    }
    result.update(changes)
    return result


def linked_plan_body(governance_id, based_on_protocol_id=None, **changes):
    """A fabricated v2 plan pins policy without copying its private contents."""
    body = {
        "request_id": str(uuid4()),
        "protocol_schema_version": "2.0",
        "based_on_protocol_id": based_on_protocol_id,
        "governance_id": governance_id,
        "title": "Fabricated linked plan",
        "owner_code": "STF-QA",
        "physician_codes": ["PHY-QA", "PHY-OTHER"],
        "backup_owner_code": "STF-QA",
        "backup_frequency": "manual_before_changes",
        "notes": "Fabricated planning notes.",
    }
    body.update(changes)
    return body

"""Synthetic-only test data; all databases live in TemporaryDirectory."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "cases.json"


def qa_presentation(**selector):
    return dict(selector, capture_mode="fabricated_qa", permission_receipt_id=None,
                qa_acknowledged=True)


def latest_version(catalog, case_id=None):
    case_id = case_id or catalog["versions"][0]["case_id"]
    return next(version for version in reversed(catalog["versions"])
                if version["case_id"] == case_id)


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

"""Strict, dependency-free validation and canonical snapshot serialization."""

import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import UUID

SCHEMA_VERSION = "1.2"
CASE_TEXT = {"case_id", "family_id", "version", "title", "provenance",
             "care_setting", "narrative"}
CASE_FLAGS = {"synthetic": True, "review_status": "unreviewed",
              "eligible_for_study": False, "collection_purpose": "demo"}
VALUE_FIELDS = {"physician_code", "next_action", "next_information",
                "decision_change", "rationale", "confidence"}


class ValidationError(ValueError):
    """Input cannot be represented by the documented contract."""


class Conflict(ValueError):
    """A retry or revision conflicts with an existing local record."""


class NotFound(LookupError):
    """Requested local object does not exist."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def validate_code(value, required=True):
    text_field(value, "Code", limit=128, required=required)
    stripped = value.strip()
    if not stripped and not required:
        return stripped
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", stripped):
        raise ValidationError("Codes must contain 1–40 letters, digits, underscores or hyphens.")
    return stripped


def exact_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValidationError("Missing or unexpected fields.")


def text_field(value, label, limit=5000, required=True):
    if not isinstance(value, str) or len(value) > limit:
        raise ValidationError(f"{label} must be text of at most {limit} characters.")
    if required and not value.strip():
        raise ValidationError(f"{label} is required; you may record insufficient information.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{label} contains invalid Unicode.") from exc
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ValidationError(f"{label} contains unsupported control characters.")
    return value


def validate_id(value):
    if not isinstance(value, str):
        raise ValidationError("Expected a UUID identifier.")
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except ValueError as exc:
        raise ValidationError("Expected a canonical UUID identifier.") from exc
    return value


def validate_case(value):
    exact_keys(value, CASE_TEXT | CASE_FLAGS.keys() | {"decision_time_facts"})
    for key in CASE_TEXT:
        text_field(value[key], key, limit=12000)
    for key in ("case_id", "family_id", "version"):
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", value[key]):
            raise ValidationError(f"Invalid {key}.")
    for key, required in CASE_FLAGS.items():
        if key == "review_status" and value[key] in ("unreviewed", "approved", "needs_revision", "rejected"):
            continue
        if type(value[key]) is not type(required) or value[key] != required:
            raise ValidationError("Cases must be synthetic, unreviewed, ineligible demo fixtures.")
    facts = value["decision_time_facts"]
    if not isinstance(facts, list) or not 1 <= len(facts) <= 40:
        raise ValidationError("Expected between 1 and 40 visible decision-time facts.")
    for fact in facts:
        exact_keys(fact, {"label", "value"})
        text_field(fact["label"], "Fact label", limit=200)
        text_field(fact["value"], "Fact value", limit=2000)
    return value


def validate_values(value):
    exact_keys(value, VALUE_FIELDS)
    for key in VALUE_FIELDS - {"confidence"}:
        text_field(value[key], key.replace("_", " "),
                   limit=128 if key == "physician_code" else 5000,
                   required=key != "rationale")
    validate_code(value["physician_code"])
    if value["confidence"] is not None and value["confidence"] not in ("low", "moderate", "high"):
        raise ValidationError("Decision confidence must be low, moderate, high, or omitted.")
    return value


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def snapshot_hash(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("Duplicate JSON keys are not accepted.")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValidationError("Non-finite JSON numbers are not accepted.")


def read_json(value):
    try:
        return json.loads(value, object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValidationError("Malformed JSON.") from exc

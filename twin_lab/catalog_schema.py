"""Case-catalog validation and immutable SQLite schema."""

import re
from datetime import date, datetime, timezone

from .schemas import (
    CASE_FLAGS,
    ValidationError,
    canonical_json,
    exact_keys,
    read_json,
    text_field,
    validate_case,
    validate_code,
    validate_id,
)

REVIEW_FIELDS = {
    "request_id",
    "version_id",
    "reviewer_code",
    "reviewed_on",
    "comments",
    "disposition",
    "supersedes_review_id",
}
VERSION_FIELDS = {
    "request_id",
    "based_on_version_id",
    "version",
    "editor_code",
    "change_note",
    "snapshot",
}
DISPOSITIONS = {"approved", "needs_revision", "rejected"}


def review_values(body):
    exact_keys(body, REVIEW_FIELDS)
    validate_id(body["request_id"])
    validate_id(body["version_id"])
    if body["supersedes_review_id"] is not None:
        validate_id(body["supersedes_review_id"])
    reviewer = validate_code(body["reviewer_code"])
    text_field(body["comments"], "Review comments")
    text_field(body["reviewed_on"], "Review date", limit=10)
    try:
        reviewed = date.fromisoformat(body["reviewed_on"])
    except ValueError as exc:
        raise ValidationError("Review date must be YYYY-MM-DD.") from exc
    if reviewed.isoformat() != body["reviewed_on"]:
        raise ValidationError("Review date must be YYYY-MM-DD.")
    if reviewed > datetime.now(timezone.utc).date():
        raise ValidationError("Review date cannot be in the future (UTC).")
    if not isinstance(body["disposition"], str) or body["disposition"] not in DISPOSITIONS:
        raise ValidationError("Choose approved, needs_revision, or rejected.")
    return reviewer


def version_values(body):
    exact_keys(body, VERSION_FIELDS)
    validate_id(body["request_id"])
    validate_id(body["based_on_version_id"])
    editor = validate_code(body["editor_code"])
    text_field(body["change_note"], "Change note")
    if not isinstance(body["version"], str) or not re.fullmatch(
        r"[A-Za-z0-9._-]{1,64}", body["version"]
    ):
        raise ValidationError(
            "Version must contain 1–64 letters, digits, dots, underscores or hyphens."
        )
    return editor


def matched_variant(family, base):
    exact_keys(
        family,
        {
            "family_id",
            "title",
            "base_case_id",
            "base_version",
            "variant_case_id",
            "variant_title",
            "factor_label",
            "fact_label",
            "base_value",
            "variant_value",
            "held_constant",
        },
    )
    for key in set(family) - {"held_constant"}:
        text_field(family[key], key, limit=2000)
    if not isinstance(family["held_constant"], list) or not family["held_constant"]:
        raise ValidationError("Matched families must declare held-constant information.")
    for item in family["held_constant"]:
        text_field(item, "Held constant", limit=200)
    if family["family_id"] != base["family_id"] or family["variant_case_id"] == base["case_id"]:
        raise ValidationError("Matched variants must share a family and have a new case identity.")
    variant = read_json(canonical_json(base))
    matches = [
        fact for fact in variant["decision_time_facts"] if fact["label"] == family["fact_label"]
    ]
    if len(matches) != 1 or matches[0]["value"] != family["base_value"]:
        raise ValidationError("Matched-family declaration does not match its base fact.")
    if family["variant_value"] == family["base_value"]:
        raise ValidationError("A matched variant must change its declared fact.")
    matches[0]["value"] = family["variant_value"]
    variant.update(CASE_FLAGS)
    variant.update(
        case_id=family["variant_case_id"],
        title=family["variant_title"],
        provenance="Newly authored synthetic UI/demo placeholder for Twin Lab v0.2; "
        "not from patient records or an original case workbook. "
        "Unreviewed; not eligible for study.",
    )
    return validate_case(variant)

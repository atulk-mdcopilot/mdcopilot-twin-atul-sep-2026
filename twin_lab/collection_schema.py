"""Collection rules are drafts, never study authorization or proof of consent."""

from .schemas import exact_keys, text_field, validate_code, validate_id, ValidationError

PROTOCOL_FIELDS = {"request_id", "based_on_protocol_id", "title", "owner_code",
                   "physician_codes", "consent_statement", "consent_version",
                   "retention_days", "backup_owner_code", "backup_frequency",
                   "backup_retention_days", "notes"}
GOVERNANCE_FIELDS = ("owner_code", "physician_codes", "consent_statement",
                     "consent_version", "retention_days", "backup_owner_code",
                     "backup_retention_days")
FREQUENCIES = ("manual_before_changes", "daily_when_collecting", "weekly_when_collecting")


def validate_protocol(body):
    exact_keys(body, PROTOCOL_FIELDS)
    validate_id(body["request_id"])
    if body["based_on_protocol_id"] is not None:
        validate_id(body["based_on_protocol_id"])
    text_field(body["title"], "Plan title", limit=200)
    for key in ("owner_code", "backup_owner_code"):
        validate_code(body[key], required=False)
    for key in ("consent_statement", "consent_version", "notes"):
        text_field(body[key], key.replace("_", " "),
                   limit=12000 if key == "consent_statement" else 5000, required=False)
    codes = body["physician_codes"]
    if not isinstance(codes, list) or len(codes) > 200:
        raise ValidationError("Enter at most 200 physician codes.")
    normalized = [validate_code(code) for code in codes]
    if len(normalized) != len(set(normalized)):
        raise ValidationError("Physician codes must be unique.")
    for key in ("retention_days", "backup_retention_days"):
        value = body[key]
        if value is not None and (type(value) is not int or not 1 <= value <= 3650):
            raise ValidationError("Retention days must be an integer from 1 to 3650 or unset.")
    if body["backup_frequency"] not in FREQUENCIES:
        raise ValidationError("Choose one of the supported backup planning frequencies.")
    return body


def validate_assignment(body):
    exact_keys(body, {"request_id", "protocol_id", "physician_code", "version_id", "notes"})
    for key in ("request_id", "protocol_id", "version_id"):
        validate_id(body[key])
    validate_code(body["physician_code"])
    text_field(body["notes"], "Assignment notes", required=False)
    return body

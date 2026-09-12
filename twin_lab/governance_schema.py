"""Strict local demo governance inputs; absent decisions stay absent."""

from datetime import date, datetime, timezone

from .schemas import ValidationError, exact_keys, text_field, validate_code, validate_id

ROLES = ("OWN-PROJ", "OWN-CLIN", "OWN-ENG", "OWN-DATA", "OWN-PRIV", "OWN-QA")
CONTROL_FLAGS = ("storage_access_verified", "device_encryption_verified",
                 "no_network_verified", "lifecycle_verified", "backup_restore_verified",
                 "external_copy_control_verified")
RETENTION_DAYS = ("response_days", "after_close_days", "withdrawal_days", "export_days",
                  "backup_days", "backup_after_deletion_days", "permission_after_close_days",
                  "audit_after_close_days")
GOVERNANCE_FIELDS = {"request_id", "based_on_governance_id", "title", "status", "operator",
                     "permission", "retention", "owners", "controls", "approved_by_code",
                     "approval_note"}


def _timestamp(value, label):
    text_field(value, label, limit=64, required=False)
    if not value:
        return
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed > datetime.now(timezone.utc):
            raise ValueError
    except ValueError as exc:
        raise ValidationError(f"{label} must include a timezone and cannot be in the future.") from exc


def validate_governance(body):
    exact_keys(body, GOVERNANCE_FIELDS)
    validate_id(body["request_id"])
    if body["based_on_governance_id"] is not None:
        validate_id(body["based_on_governance_id"])
    text_field(body["title"], "Governance title", limit=200)
    if body["status"] not in ("draft", "approved", "revoked"):
        raise ValidationError("Choose draft, approved, or revoked governance.")
    validate_code(body["approved_by_code"], required=False)
    text_field(body["approval_note"], "Review determination and approval note", required=False)
    operator = body["operator"]
    exact_keys(operator, {"legal_name", "project_contact", "privacy_contact", "pilot_close_date"})
    for key in operator:
        text_field(operator[key], key.replace("_", " "), limit=1000, required=False)
    if operator["pilot_close_date"]:
        try:
            parsed = date.fromisoformat(operator["pilot_close_date"])
            if parsed.isoformat() != operator["pilot_close_date"]:
                raise ValueError
        except ValueError as exc:
            raise ValidationError("Pilot close date must use YYYY-MM-DD.") from exc
    exact_keys(body["permission"], {"version", "text"})
    text_field(body["permission"]["version"], "Permission version", limit=128, required=False)
    text_field(body["permission"]["text"], "Exact participant notice", limit=20000, required=False)
    retention = body["retention"]
    exact_keys(retention, {"version", *RETENTION_DAYS})
    text_field(retention["version"], "Retention policy version", limit=128, required=False)
    for key in RETENTION_DAYS:
        if retention[key] is not None and (type(retention[key]) is not int or not 1 <= retention[key] <= 3650):
            raise ValidationError("Retention periods must be whole days from 1 to 3650, or unset.")
    owners = body["owners"]
    if not isinstance(owners, list) or len(owners) > len(ROLES):
        raise ValidationError("Record at most six local demo role appointments.")
    seen = []
    for owner in owners:
        exact_keys(owner, {"role_code", "actor_code", "person_name", "contact", "accepted_at"})
        if owner["role_code"] not in ROLES or owner["role_code"] in seen:
            raise ValidationError("Owner roles must be supported and unique.")
        seen.append(owner["role_code"])
        validate_code(owner["actor_code"], required=False)
        for key in ("person_name", "contact"):
            text_field(owner[key], key.replace("_", " "), limit=1000, required=False)
        _timestamp(owner["accepted_at"], "Role acceptance time")
    controls = body["controls"]
    exact_keys(controls, {"actor_code", "checked_at", "evidence", *CONTROL_FLAGS})
    validate_code(controls["actor_code"], required=False)
    _timestamp(controls["checked_at"], "Controls check time")
    text_field(controls["evidence"], "Controls verification evidence", required=False)
    if any(type(controls[key]) is not bool for key in CONTROL_FLAGS):
        raise ValidationError("Control attestations must be true or false.")
    return body


def missing_fields(record, include_status=True):
    """A complete attestation is not an independent verification of its claims."""
    if not record:
        return ["governance"]
    missing = []
    if include_status and record["status"] != "approved":
        missing.append("approved_governance")
    for key, value in record["operator"].items():
        if not value.strip():
            missing.append(f"operator.{key}")
    close = record["operator"]["pilot_close_date"]
    if close and date.fromisoformat(close) < datetime.now(timezone.utc).date():
        missing.append("operator.pilot_close_date_expired")
    for key, value in record["permission"].items():
        if not value.strip():
            missing.append(f"permission.{key}")
    for key, value in record["retention"].items():
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(f"retention.{key}")
    owners = {owner["role_code"]: owner for owner in record["owners"]}
    for role in ROLES:
        if role not in owners or any(not value.strip() for value in owners[role].values()):
            missing.append(f"accepted_owner.{role}")
    controls = record["controls"]
    for key, value in controls.items():
        if not (value.strip() if isinstance(value, str) else value):
            missing.append(f"controls.{key}")
    accepted_actors = {owner["actor_code"].strip() for owner in owners.values() if owner["accepted_at"]}
    if controls["actor_code"].strip() not in accepted_actors:
        missing.append("controls.accepted_actor")
    approver = record["approved_by_code"].strip()
    if not approver or approver != owners.get("OWN-PRIV", {}).get("actor_code", "").strip():
        missing.append("approved_by_privacy_owner")
    if not record["approval_note"].strip():
        missing.append("approval_note")
    return missing


def validate_permission(body):
    exact_keys(body, {"request_id", "governance_id", "physician_code", "choice"})
    validate_id(body["request_id"])
    validate_id(body["governance_id"])
    validate_code(body["physician_code"])
    if body["choice"] not in ("agree", "decline"):
        raise ValidationError("Choose Agree or Decline; neither is selected automatically.")
    return body

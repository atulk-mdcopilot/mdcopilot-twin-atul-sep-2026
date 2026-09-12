"""Visible administrative-retention obligations that require custodian review."""

from datetime import datetime, time, timedelta, timezone

from .lifecycle import instant


def administrative_review(lifecycle, db, at):
    table_names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "governance_versions" not in table_names:
        return {"overdue_permissions": [], "overdue_governance": [], "overdue_audit_events": []}
    versions = {row["governance_id"]: row for row in lifecycle.rows(db, "governance_versions")}
    responses = lifecycle.rows(db, "responses")

    def due(version, field):
        close = version.get("operator", {}).get("pilot_close_date")
        days = version.get("retention", {}).get(field)
        if not close or not days or version.get("status") != "approved":
            return None
        return datetime.combine(datetime.fromisoformat(close).date(), time.max,
                                tzinfo=timezone.utc) + timedelta(days=days)

    permissions = []
    for receipt in lifecycle.rows(db, "permission_receipts"):
        deadline = due(versions[receipt["governance_id"]], "permission_after_close_days")
        if deadline and deadline <= instant(at):
            permissions.append({"receipt_id": receipt["receipt_id"], "expires_at": deadline.isoformat(),
                "linked_response_ids": [row["response_id"] for row in responses
                                        if row.get("permission_receipt_id") == receipt["receipt_id"]]})
    governance = []
    for identifier, version in versions.items():
        deadlines = [due(version, field) for field in ("permission_after_close_days", "audit_after_close_days")]
        if all(deadlines) and max(deadlines) <= instant(at):
            governance.append({"governance_id": identifier, "expires_at": max(deadlines).isoformat()})
    metadata = {row["root_response_id"]: row for row in lifecycle.rows(db, "response_lifecycle")}
    audit = []
    for event in lifecycle.events(db):
        roots = event.get("root_ids", list(event.get("deadlines", {})))
        deadlines = [due(versions.get(metadata.get(root, {}).get("governance_id"), {}), "audit_after_close_days")
                     for root in roots]
        if deadlines and all(deadlines) and max(deadlines) <= instant(at):
            audit.append({"event_id": event["event_id"], "expires_at": max(deadlines).isoformat()})
    return {"overdue_permissions": permissions, "overdue_governance": governance,
            "overdue_audit_events": audit,
            "handling": "Custodian review required. Administrative records and authoritative journals are not automatically deleted; resolve retained records and old copies before retirement."}

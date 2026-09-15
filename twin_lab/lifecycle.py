"""Local response restrictions and immutable, content-free lifecycle metadata."""

import json
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from .persistence import get_record, read_records
from .schemas import (
    Conflict,
    NotFound,
    ValidationError,
    canonical_json,
    exact_keys,
    now,
    text_field,
    validate_code,
    validate_id,
)


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValidationError("Lifecycle timestamps require a timezone.")
    return result.astimezone(timezone.utc)


def expiry(anchor: str, governance: dict) -> str:
    """The approved policy is frozen at original submission, never at correction."""
    policy = governance["retention"]
    close = datetime.combine(
        datetime.fromisoformat(governance["operator"]["pilot_close_date"]).date(),
        time.max,
        tzinfo=timezone.utc,
    )
    return min(
        instant(anchor) + timedelta(days=policy["response_days"]),
        close + timedelta(days=policy["after_close_days"]),
    ).isoformat()


class Lifecycle:
    def __init__(self, store):
        self.store = store
        self.clock = now
        self.ledger_path = store.db_path.parent / "deletion-ledger.jsonl"

    def events(self, db):
        from .lifecycle_files import restriction_entries

        events = {item["event_id"]: item for item in read_records(db, "lifecycle_events")}
        events.update(
            {
                item["event"]["event_id"]: item["event"]
                for item in restriction_entries(self.ledger_path.parent)
            }
        )
        return list(events.values())

    def root_for(self, db, response_id):
        visited = set()
        while response_id not in visited:
            visited.add(response_id)
            response = get_record(db, "responses", response_id)
            if not response["supersedes_response_id"]:
                return response
            response_id = response["supersedes_response_id"]
        raise RuntimeError("Invalid response revision chain.")

    def attach(self, db, response, governance=None, permission_receipt_id=None):
        if response["supersedes_response_id"]:
            return self.metadata(db, response["supersedes_response_id"])
        metadata = {
            "root_response_id": response["response_id"],
            "retention_anchor_at": response["submitted_at"],
            "expires_at": None,
            "permission_status": "fabricated_qa"
            if response.get("capture_mode") == "fabricated_qa"
            else "unknown_legacy",
            "permission_receipt_id": permission_receipt_id,
            "governance_id": None,
            "policy": None,
        }
        if governance is not None and permission_receipt_id:
            metadata.update(
                permission_status="recorded",
                governance_id=governance["governance_id"],
                expires_at=expiry(response["submitted_at"], governance),
                policy=dict(governance["retention"]),
            )
        db.execute(
            "INSERT INTO response_lifecycle(id,payload) VALUES (?,?)",
            (response["response_id"], canonical_json(metadata)),
        )
        return metadata

    def metadata(self, db, response_id):
        root = self.root_for(db, response_id)
        row = db.execute(
            "SELECT payload FROM response_lifecycle WHERE id=?", (root["response_id"],)
        ).fetchone()
        if row:
            return json.loads(row[0])
        return {
            "root_response_id": root["response_id"],
            "retention_anchor_at": root["submitted_at"],
            "expires_at": None,
            "permission_status": "unknown_legacy",
            "permission_receipt_id": None,
            "governance_id": None,
            "policy": None,
        }

    def is_blocked(self, db, physician_code, receipt_id=None):
        from .lifecycle_files import ledger_entries

        ledger_entries(self.ledger_path)
        return any(
            event["kind"] == "withdrawal" and event["physician_code"] == physician_code
            for event in self.events(db)
        )

    def require_capture(self, db, physician_code, receipt_id=None):
        if self.is_blocked(db, physician_code, receipt_id):
            raise Conflict("A withdrawal receipt blocks further capture for this physician code.")

    def restriction(self, db, response_id, at=None):
        from .lifecycle_files import ledger_entries

        root = self.root_for(db, response_id)
        identifier = root["response_id"]
        if any(identifier in item["root_ids"] for item in ledger_entries(self.ledger_path)):
            return "disposal_recorded"
        events = self.events(db)
        released = {item["hold_id"] for item in events if item["kind"] == "hold_release"}
        if any(
            item["kind"] == "hold"
            and item["hold_id"] not in released
            and identifier in item["root_ids"]
            for item in events
        ):
            return "legal_hold"
        if self.is_blocked(db, root["physician_code"]):
            return "withdrawn"
        metadata = self.metadata(db, identifier)
        if metadata["expires_at"] and instant(metadata["expires_at"]) <= instant(
            at or self.clock()
        ):
            return "expired"
        return None

    def normal_use(self, db, response_id, at=None):
        return self.restriction(db, response_id, at) is None

    def _event(self, db, kind, body, payload):
        from .lifecycle_files import append_ledger, restriction_entries

        previous = db.execute(
            "SELECT request_body,payload FROM lifecycle_events WHERE request_id=?",
            (body["request_id"],),
        ).fetchone()
        if previous:
            if previous[0] != canonical_json(dict(body, event_kind=kind)):
                raise Conflict("This lifecycle request was already recorded with different values.")
            return json.loads(previous[1]), True
        frozen_body = canonical_json(dict(body, event_kind=kind))
        journal = next(
            (
                item
                for item in restriction_entries(self.ledger_path.parent)
                if item["request_id"] == body["request_id"]
            ),
            None,
        )
        if journal and journal["request_body"] != frozen_body:
            raise Conflict("This lifecycle request was already journaled with different values.")
        event = (
            journal["event"]
            if journal
            else dict(
                payload,
                kind=kind,
                request_id=body["request_id"],
                event_id=str(uuid4()),
                recorded_at=self.clock(),
            )
        )
        if not journal:
            append_ledger(
                self.ledger_path.parent / "lifecycle-events.jsonl",
                {"request_id": body["request_id"], "request_body": frozen_body, "event": event},
            )
        db.execute(
            "INSERT INTO lifecycle_events(id,request_id,kind,request_body,payload) VALUES (?,?,?,?,?)",
            (event["event_id"], body["request_id"], kind, frozen_body, canonical_json(event)),
        )
        return event, False

    def withdraw(self, body):
        exact_keys(body, {"request_id", "physician_code", "actor_code"})
        validate_id(body["request_id"])
        code, actor = validate_code(body["physician_code"]), validate_code(body["actor_code"])
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            roots = sorted(
                {
                    self.root_for(db, row["response_id"])["response_id"]
                    for row in read_records(db, "responses")
                    if row["physician_code"] == code
                }
            )
            return self._event(
                db,
                "withdrawal",
                body,
                {
                    "withdrawal_id": body["request_id"],
                    "physician_code": code,
                    "actor_code": actor,
                    "root_ids": roots,
                    "received_at": self.clock(),
                },
            )

    def verify_withdrawal(self, body):
        exact_keys(
            body,
            {
                "request_id",
                "withdrawal_id",
                "actor_code",
                "verification_attested",
                "withdrawal_days",
            },
        )
        validate_id(body["request_id"])
        validate_id(body["withdrawal_id"])
        actor = validate_code(body["actor_code"])
        days = body["withdrawal_days"]
        if body["verification_attested"] is not True or (
            days is not None and (type(days) is not int or not 1 <= days <= 3650)
        ):
            raise ValidationError(
                "Reasonable verification must be attested; provide valid days or null for policy."
            )
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM lifecycle_events WHERE request_id=?", (body["request_id"],)
            ).fetchone():
                return self._event(db, "verification", body, {})
            events = self.events(db)
            withdrawal = next(
                (
                    item
                    for item in events
                    if item["kind"] == "withdrawal"
                    and item["withdrawal_id"] == body["withdrawal_id"]
                ),
                None,
            )
            if not withdrawal:
                raise NotFound("Withdrawal receipt was not found.")
            existing = next(
                (
                    item
                    for item in events
                    if item["kind"] == "verification"
                    and item["withdrawal_id"] == body["withdrawal_id"]
                ),
                None,
            )
            if existing and existing.get("request_id") != body["request_id"]:
                raise Conflict("This withdrawal has already been verified.")
            deadlines, unavailable = {}, []
            for root_id in withdrawal["root_ids"]:
                if not db.execute("SELECT 1 FROM responses WHERE id=?", (root_id,)).fetchone():
                    # A restored snapshot may predate this chain, or ordinary
                    # retention disposal may already have removed its content.
                    unavailable.append(root_id)
                    continue
                metadata = self.metadata(db, root_id)
                policy_days = metadata["policy"]["withdrawal_days"] if metadata["policy"] else days
                if policy_days is None:
                    raise ValidationError(
                        "Legacy records need an explicitly chosen withdrawal deadline."
                    )
                deadline = instant(self.clock()) + timedelta(days=policy_days)
                if metadata["expires_at"]:
                    deadline = min(deadline, instant(metadata["expires_at"]))
                deadlines[root_id] = deadline.isoformat()
            return self._event(
                db,
                "verification",
                body,
                {
                    "withdrawal_id": body["withdrawal_id"],
                    "actor_code": actor,
                    "verification_attested": True,
                    "verified_at": self.clock(),
                    "deadlines": deadlines,
                    "unavailable_root_ids": unavailable,
                    "withdrawal_days": days,
                },
            )

    def hold(self, body):
        exact_keys(body, {"request_id", "response_ids", "actor_code", "authority_record"})
        validate_id(body["request_id"])
        actor = validate_code(body["actor_code"])
        text_field(body["authority_record"], "Hold authority record", limit=1000)
        if not isinstance(body["response_ids"], list) or not 1 <= len(body["response_ids"]) <= 1000:
            raise ValidationError("A hold requires an explicit nonempty list of response IDs.")
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM lifecycle_events WHERE request_id=?", (body["request_id"],)
            ).fetchone():
                return self._event(db, "hold", body, {})
            roots = sorted(
                {
                    self.root_for(db, validate_id(identifier))["response_id"]
                    for identifier in body["response_ids"]
                }
            )
            if any(self.restriction(db, root) == "disposal_recorded" for root in roots):
                raise Conflict(
                    "Disposal is already recorded for this response; recover the pending disposal first."
                )
            return self._event(
                db,
                "hold",
                body,
                {
                    "hold_id": body["request_id"],
                    "root_ids": roots,
                    "response_ids": list(body["response_ids"]),
                    "actor_code": actor,
                    "authority_record": body["authority_record"],
                    "created_at": self.clock(),
                },
            )

    def release_hold(self, body):
        exact_keys(body, {"request_id", "hold_id", "actor_code", "authority_record"})
        validate_id(body["request_id"])
        validate_id(body["hold_id"])
        validate_code(body["actor_code"])
        text_field(body["authority_record"], "Release authority record", limit=1000)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not any(
                item["kind"] == "hold" and item["hold_id"] == body["hold_id"]
                for item in self.events(db)
            ):
                raise NotFound("Hold was not found.")
            return self._event(
                db, "hold_release", body, {key: body[key] for key in body if key != "request_id"}
            )

    def overview(self):
        from .lifecycle_files import inventory, plan_disposal

        with self.store.connection() as db:
            db.execute("BEGIN")
            grouped: dict[str, dict] = {}
            for response in read_records(db, "responses"):
                metadata = self.metadata(db, response["response_id"])
                grouped.setdefault(metadata["root_response_id"], dict(metadata, response_ids=[]))[
                    "response_ids"
                ].append(response["response_id"])
            records = list(grouped.values())
            for record in records:
                record.pop("policy", None)
                record["restriction"] = self.restriction(db, record["root_response_id"])
                record["ordinary_use_allowed"] = record["restriction"] is None
            events = self.events(db)
            copies = inventory(self, db)
        return {
            "records": records,
            "withdrawals": [item for item in events if item["kind"] == "withdrawal"],
            "verifications": [item for item in events if item["kind"] == "verification"],
            "holds": [item for item in events if item["kind"] in ("hold", "hold_release")],
            **copies,
            "disposal": plan_disposal(self),
        }

    def managed_export(self, payload):
        from .lifecycle_files import managed_export

        return managed_export(self, payload)

    def plan_disposal(self, at=None):
        from .lifecycle_files import plan_disposal

        return plan_disposal(self, at)

    def apply_disposal(self, plan, actor_code):
        from .lifecycle_files import apply_disposal

        return apply_disposal(self, plan, actor_code)

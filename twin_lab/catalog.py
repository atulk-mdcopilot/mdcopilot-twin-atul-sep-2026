"""Immutable, version-bound synthetic case authoring and local review."""

from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from .catalog_schema import matched_variant, review_values, version_values
from .persistence import find_retry, get_record
from .schemas import (
    CASE_FLAGS,
    Conflict,
    NotFound,
    ValidationError,
    canonical_json,
    now,
    read_json,
    snapshot_hash,
    validate_case,
    validate_id,
)

FAMILIES = Path(__file__).resolve().parent.parent / "fixtures" / "families.json"
MISSING_RECORD = "The requested catalog record was not found."
RETRY_CONFLICT = "This request ID was already used for different content. Reload before retrying."


def _latest(db, case_id):
    row = db.execute(
        "SELECT payload FROM case_versions WHERE case_id = ? ORDER BY rowid DESC LIMIT 1",
        (case_id,),
    ).fetchone()
    if row is None:
        raise NotFound("Synthetic case not found.")
    return read_json(row[0])


def _latest_review(db, version_id):
    row = db.execute(
        "SELECT payload FROM case_reviews WHERE version_id = ? ORDER BY rowid DESC LIMIT 1",
        (version_id,),
    ).fetchone()
    return read_json(row[0]) if row else None


def _with_review(db, version):
    return {**version, "latest_review": _latest_review(db, version["version_id"])}


class Catalog:
    def __init__(self, connection_factory):
        self.connection = connection_factory

    def initialize(self, cases, include_families=True, *, db=None):
        """Seed immutable fixtures separately from schema setup, using one transaction."""
        if db is None:
            with self.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self.initialize(cases, include_families=include_families, db=connection)
            return
        for case in cases:
            self._seed_case(db, case)
        if include_families:
            self._seed_families(db)
            self._seed_wording_revision(db)

    def _seed_wording_revision(self, db):
        # Version 1.0 is already referenced by observations and matched families.
        # Append the requested copy edit once, without replacing local revisions.
        sources = db.execute("""SELECT payload FROM case_versions
            WHERE version_label = '1.0' AND request_id IS NULL""").fetchall()
        for row in sources:
            source = read_json(row[0])
            if _latest(db, source["case_id"])["version_id"] != source["version_id"]:
                continue
            snapshot = source["snapshot"]
            snapshot["narrative"] = snapshot["narrative"].replace("fictional ", "")
            for fact in snapshot["decision_time_facts"]:
                fact["value"] = fact["value"].replace("fictional ", "")
            snapshot["version"] = "1.1"
            validate_case(snapshot)
            identifier = str(uuid5(NAMESPACE_URL, f"twin-lab/case/{source['case_id']}/1.1"))
            self._insert_version(
                db,
                snapshot,
                identifier,
                None,
                "Source wording revision: remove 'fictional' from the narrative and facts; "
                "synthetic provenance and clinical values retained.",
                source["version_id"],
            )

    @staticmethod
    def _insert_version(
        db, snapshot, identifier, editor, note, based_on, request_id=None, request_body=None
    ):
        record = {
            "version_id": identifier,
            "case_id": snapshot["case_id"],
            "case_version": snapshot["version"],
            "snapshot": snapshot,
            "snapshot_sha256": snapshot_hash(snapshot),
            "created_at": now(),
            "editor_code": editor,
            "change_note": note,
            "based_on_version": based_on,
        }
        db.execute(
            """INSERT INTO case_versions
            (id, case_id, version_label, based_on_id, request_id, request_body, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                identifier,
                record["case_id"],
                record["case_version"],
                based_on,
                request_id,
                request_body,
                canonical_json(record),
            ),
        )
        return record

    def _seed_case(self, db, case):
        validate_case(case)
        if any(case[key] != value for key, value in CASE_FLAGS.items()):
            raise ValidationError(
                "Source fixtures must remain synthetic, unreviewed, ineligible demos."
            )
        snapshot = read_json(canonical_json(case))
        previous = db.execute(
            "SELECT payload FROM case_versions WHERE case_id = ? AND version_label = ?",
            (case["case_id"], case["version"]),
        ).fetchone()
        if previous:
            record = read_json(previous[0])
            if record["snapshot"] != snapshot:
                raise Conflict(
                    "A source fixture changed an existing case version. Restore it or give it a new version."
                )
            return record
        latest_row = db.execute(
            "SELECT payload FROM case_versions WHERE case_id = ? ORDER BY rowid DESC LIMIT 1",
            (case["case_id"],),
        ).fetchone()
        latest = read_json(latest_row[0]) if latest_row else None
        if latest and latest["snapshot"]["family_id"] != snapshot["family_id"]:
            raise Conflict("A source revision must retain its case family.")
        identifier = str(uuid5(NAMESPACE_URL, f"twin-lab/case/{case['case_id']}/{case['version']}"))
        return self._insert_version(
            db,
            snapshot,
            identifier,
            None,
            "Imported synthetic, unreviewed source fixture.",
            latest["version_id"] if latest else None,
        )

    def _seed_families(self, db):
        families = read_json(FAMILIES.read_text(encoding="utf-8"))
        if not isinstance(families, list) or len(families) != 5:
            raise ValidationError("Expected exactly five matched demo families.")
        family_ids, base_ids, variant_ids = set(), set(), set()
        for family in families:
            if not isinstance(family, dict):
                raise ValidationError("Matched-family declarations must be objects.")
            base_row = db.execute(
                "SELECT payload FROM case_versions WHERE case_id = ? AND version_label = ?",
                (family.get("base_case_id"), family.get("base_version")),
            ).fetchone()
            if base_row is None:
                raise ValidationError("Matched family is missing its pinned source version.")
            base = read_json(base_row[0])
            variant = self._seed_case(db, matched_variant(family, base["snapshot"]))
            if (
                family["family_id"] in family_ids
                or base["case_id"] in base_ids
                or variant["case_id"] in variant_ids
            ):
                raise ValidationError("Each matched family must have a unique base and variant.")
            family_ids.add(family["family_id"])
            base_ids.add(base["case_id"])
            variant_ids.add(variant["case_id"])
            record = {
                "family_id": family["family_id"],
                "title": family["title"],
                "factor_label": family["factor_label"],
                "base_version_id": base["version_id"],
                "variant_version_id": variant["version_id"],
                "held_constant": family["held_constant"],
                "changed_fact": {
                    "label": family["fact_label"],
                    "base_value": family["base_value"],
                    "variant_value": family["variant_value"],
                },
            }
            payload = canonical_json(record)
            existing = db.execute(
                "SELECT payload FROM case_families WHERE id = ?", (record["family_id"],)
            ).fetchone()
            if existing:
                if existing[0] != payload:
                    raise Conflict("A source family changed an existing immutable comparison.")
            else:
                db.execute(
                    "INSERT INTO case_families(id, payload) VALUES (?, ?)",
                    (record["family_id"], payload),
                )

    def overview(self):
        with self.connection() as db:
            db.execute("BEGIN")
            versions = [
                _with_review(db, read_json(row[0]))
                for row in db.execute("SELECT payload FROM case_versions ORDER BY rowid")
            ]
            reviews = [
                read_json(row[0])
                for row in db.execute("SELECT payload FROM case_reviews ORDER BY rowid")
            ]
            families = [
                read_json(row[0])
                for row in db.execute("SELECT payload FROM case_families ORDER BY rowid")
            ]
            return {"versions": versions, "reviews": reviews, "families": families}

    def cases(self):
        with self.connection() as db:
            db.execute("BEGIN")
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT case_id FROM case_versions GROUP BY case_id ORDER BY MIN(rowid)"
                )
            ]
            return [self.resolve(db, case_id=case_id)["case_snapshot"] for case_id in ids]

    def resolve(self, db, case_id=None, version_id=None):
        if (case_id is None) == (version_id is None):
            raise ValidationError("Choose either a case or an exact case version.")
        if version_id is not None:
            validate_id(version_id)
            version = get_record(
                db, "case_versions", version_id, missing=MISSING_RECORD, decode=read_json
            )
        else:
            if not isinstance(case_id, str):
                raise ValidationError("Case identifier must be text.")
            version = _latest(db, case_id)
        review = _latest_review(db, version["version_id"])
        snapshot = version["snapshot"]
        snapshot["review_status"] = review["disposition"] if review else "unreviewed"
        snapshot["eligible_for_study"] = False
        return {
            "case_snapshot": snapshot,
            "case_version_id": version["version_id"],
            "case_review_id": review["review_id"] if review else None,
        }

    def add_review(self, body):
        reviewer = review_values(body)
        request_body = canonical_json(body)
        body = read_json(request_body)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            duplicate = find_retry(
                db,
                "case_reviews",
                body["request_id"],
                request_body,
                conflict=RETRY_CONFLICT,
                decode=read_json,
            )
            if duplicate:
                return duplicate, True
            get_record(
                db, "case_versions", body["version_id"], missing=MISSING_RECORD, decode=read_json
            )
            latest = _latest_review(db, body["version_id"])
            expected = latest["review_id"] if latest else None
            if body["supersedes_review_id"] != expected:
                raise Conflict("The review changed. Reload and supersede its latest review.")
            record = {
                **body,
                "review_id": str(uuid4()),
                "reviewer_code": reviewer,
                "recorded_at": now(),
            }
            db.execute(
                """INSERT INTO case_reviews
                (id, version_id, supersedes_id, request_id, request_body, payload)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    record["review_id"],
                    record["version_id"],
                    expected,
                    body["request_id"],
                    request_body,
                    canonical_json(record),
                ),
            )
        return record, False

    def add_version(self, body):
        editor = version_values(body)
        validate_case(body["snapshot"])
        request_body = canonical_json(body)
        body = read_json(request_body)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            duplicate = find_retry(
                db,
                "case_versions",
                body["request_id"],
                request_body,
                conflict=RETRY_CONFLICT,
                decode=read_json,
            )
            if duplicate:
                return _with_review(db, duplicate), True
            prior = get_record(
                db,
                "case_versions",
                body["based_on_version_id"],
                missing=MISSING_RECORD,
                decode=read_json,
            )
            if _latest(db, prior["case_id"])["version_id"] != prior["version_id"]:
                raise Conflict("This case already has a newer version. Reload before revising.")
            snapshot = body["snapshot"]
            if (
                snapshot["case_id"] != prior["case_id"]
                or snapshot["family_id"] != prior["snapshot"]["family_id"]
            ):
                raise ValidationError("A revision must retain its case and family identity.")
            if snapshot["version"] != body["version"]:
                raise ValidationError("The snapshot version must match the new version label.")
            if db.execute(
                "SELECT 1 FROM case_versions WHERE case_id = ? AND version_label = ?",
                (prior["case_id"], body["version"]),
            ).fetchone():
                raise Conflict("That case version already exists. Choose a new version label.")
            snapshot.update(CASE_FLAGS)
            record = self._insert_version(
                db,
                snapshot,
                str(uuid4()),
                editor,
                body["change_note"],
                prior["version_id"],
                body["request_id"],
                request_body,
            )
            return _with_review(db, record), False

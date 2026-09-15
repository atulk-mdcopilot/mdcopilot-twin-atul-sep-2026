"""Explicit offline maintenance; never invoked by application startup."""

import argparse
import json
import os
import sqlite3
from pathlib import Path

from .lifecycle_files import restore_snapshot
from .schemas import Conflict, NotFound, ValidationError, canonical_json, read_json
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="Twin Lab local lifecycle maintenance")
    parser.add_argument("--data-dir", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser(
        "plan", help="Preview eligible disposal without deleting anything"
    )
    plan_parser.add_argument("--output", type=Path, required=True)
    apply_parser = commands.add_parser(
        "apply", help="Apply a reviewed plan; stop the application first"
    )
    apply_parser.add_argument("--plan", type=Path, required=True)
    apply_parser.add_argument("--actor-code", required=True)
    apply_parser.add_argument(
        "--confirm", required=True, help="Exact confirmation digest from the reviewed plan"
    )
    restore_parser = commands.add_parser(
        "restore", help="Restore into a new location with current lifecycle journals"
    )
    restore_parser.add_argument("--source", type=Path, required=True)
    restore_parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.command == "restore":
            result = restore_snapshot(
                args.source, args.destination, args.data_dir / "deletion-ledger.jsonl"
            )
        else:
            database = args.data_dir / "twin-lab.sqlite3"
            if not database.is_file():
                raise ValidationError("The specified data directory has no Twin Lab database.")
            store = Store(database)
            if args.command == "plan":
                result = store.lifecycle.plan_disposal()
                with args.output.open("x", encoding="utf-8") as output:
                    output.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
                    output.flush()
                    os.fsync(output.fileno())
            else:
                plan = read_json(args.plan.read_text(encoding="utf-8"))
                if not isinstance(plan, dict) or plan.get("confirmation") != args.confirm:
                    raise ValidationError(
                        "Confirmation must match the exact reviewed disposal plan."
                    )
                result = store.lifecycle.apply_disposal(plan, args.actor_code)
        print(canonical_json(result))
    except (Conflict, NotFound, ValidationError, OSError, sqlite3.Error, RuntimeError) as exc:
        # Validation errors contain no response content; storage errors may expose
        # local paths but never stored clinical answers or credential values.
        if isinstance(exc, (Conflict, NotFound, ValidationError)):
            parser.exit(2, f"Maintenance stopped: {exc}\n")
        parser.exit(
            2,
            "Maintenance stopped: local storage or journal verification failed. No completion is claimed.\n",
        )


if __name__ == "__main__":
    main()

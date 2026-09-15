"""Explicit suite membership and machine-readable unittest evidence."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUPS = {
    "fast": ROOT / "tests",
    "compatibility": ROOT / "tests/compatibility",
    "sequences": ROOT / "tests/sequences",
    "interruptions": ROOT / "tests/interruptions",
}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item.id()


def main():
    group = sys.argv[1]
    directory = GROUPS[group]
    files = sorted(directory.glob("test_*.py"))
    if not files:
        raise SystemExit(f"PENDING: required {group} suite has no test_*.py files.")
    sys.path[:0] = [str(directory), str(ROOT / "tests"), str(ROOT)]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromName(path.stem) for path in files)
    ids = list(flatten(suite))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    details = {
        "group": group,
        "files": [str(path.relative_to(ROOT)) for path in files],
        "test_ids": ids,
        "count": result.testsRun,
        "failures": [test.id() for test, _ in result.failures],
        "errors": [test.id() for test, _ in result.errors],
        "skipped": [{"id": test.id(), "reason": reason} for test, reason in result.skipped],
        "unexpected_successes": [test.id() for test in result.unexpectedSuccesses],
        "expected_failures": [test.id() for test, _ in result.expectedFailures],
    }
    Path(f"/quality-output/{group}-results.json").write_text(json.dumps(details, indent=2))
    return int(
        not result.wasSuccessful()
        or not result.testsRun
        or bool(result.skipped)
        or bool(result.expectedFailures)
    )


if __name__ == "__main__":
    raise SystemExit(main())

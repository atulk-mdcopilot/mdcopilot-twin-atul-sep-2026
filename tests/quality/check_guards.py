"""Prove actual configured tools reject deliberate defects in disposable files."""

import subprocess
import tempfile
from pathlib import Path

from check_python import evidence_errors, required_stages

CONFIG = "/app/tests/quality/pyproject.toml"


def must_fail(label, command, expected):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    output = result.stdout + result.stderr
    if result.returncode == 0 or expected not in output:
        raise AssertionError(f"{label}: rejection not demonstrated: {output}")
    print(f"PASS guard: {label} rejected ({expected})")


def main():
    minimal = {"mode": "--fast", "host_checks": [], "reports": {}}
    if "required host stage missing, repeated or out of order" not in evidence_errors(minimal):
        raise AssertionError("Missing host stage incorrectly accepted")
    minimal["host_checks"] = [{"name": name, "exit_code": 0} for name in required_stages("--fast")]
    if "required Python checks missing or failed" not in evidence_errors(minimal):
        raise AssertionError("Missing Python report incorrectly accepted")
    if "required JavaScript checks missing or failed" not in evidence_errors(minimal):
        raise AssertionError("Missing JavaScript report incorrectly accepted")
    print("PASS guard: missing stage and required evidence rejected")
    with tempfile.TemporaryDirectory(prefix="quality-guards-") as directory:
        root = Path(directory)
        syntax = root / "syntax.py"
        syntax.write_text("def broken(:\n")
        must_fail("Python syntax", ["python", "-m", "py_compile", str(syntax)], "SyntaxError")
        unused = root / "unused.py"
        unused.write_text("import os\n")
        must_fail(
            "unused import",
            ["ruff", "check", "--no-cache", "--config", CONFIG, str(unused)],
            "F401",
        )
        typed = root / "typed.py"
        typed.write_text('count: int = "not a number"\n')
        must_fail(
            "Python type mismatch", ["mypy", "--config-file", CONFIG, str(typed)], "[assignment]"
        )
        failing = root / "test_deliberate.py"
        failing.write_text(
            "import unittest\nclass Deliberate(unittest.TestCase):\n    def test_failure(self):\n        self.fail('expected guard failure')\n"
        )
        must_fail(
            "test assertion",
            ["python", "-m", "unittest", "discover", "-s", directory],
            "FAILED (failures=1)",
        )


if __name__ == "__main__":
    main()

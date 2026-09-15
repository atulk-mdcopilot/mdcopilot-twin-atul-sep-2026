"""Offline checks and evidence. The host wrapper supplies Git metadata only."""

import hashlib
import importlib.metadata
import json
import platform
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/app")
OUTPUT = Path("/quality-output")
CONFIG = "tests/quality/pyproject.toml"


def source_files():
    return [
        ROOT / name.decode()
        for name in (OUTPUT / "source-files.bin").read_bytes().split(b"\0")
        if name
    ]


def source_hashes():
    hashes = {}
    for path in source_files():
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Source symlink escapes checkout: {path}")
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def isolation():
    config = json.loads((OUTPUT / "compose-resolved.json").read_text())
    root = (OUTPUT / "source-root.txt").read_text().strip()
    expected = {"python-checks", "js-checks", "test-server", "browser-checks"}
    if set(config["services"]) != expected:
        raise ValueError("Unexpected Compose service")
    for name, service in config["services"].items():
        expected_network = "service:test-server" if name == "browser-checks" else "none"
        if service.get("network_mode") != expected_network:
            raise ValueError(f"{name}: network isolation is required")
        if service.get("ports") or service.get("privileged") or not service.get("read_only"):
            raise ValueError(f"{name}: ports/privilege/writable root violate isolation")
        if service.get("cap_drop") != ["ALL"] or service.get("security_opt") != [
            "no-new-privileges:true"
        ]:
            raise ValueError(f"{name}: capability restrictions missing")
        mounts = service.get("volumes", [])
        expected_targets = {"/app"} if name == "test-server" else {"/app", "/quality-output"}
        if {mount["target"] for mount in mounts} != expected_targets:
            raise ValueError(f"{name}: unexpected mounted path")
        for mount in mounts:
            if mount["type"] != "bind":
                raise ValueError(f"{name}: persistent volumes are forbidden")
            if mount["target"] == "/app":
                if mount["source"] != root or not mount.get("read_only"):
                    raise ValueError(f"{name}: source must be the read-only checkout")
            else:
                destination = Path(mount["source"])
                if (
                    destination.is_relative_to(root)
                    or not destination.name.startswith("twin-lab-quality.")
                    or destination.parent not in (Path("/tmp"), Path("/private/tmp"))
                ):
                    raise ValueError(f"{name}: output must be a fresh dedicated external directory")
        if not service.get("tmpfs"):
            raise ValueError(f"{name}: disposable storage missing")
    print("PASS: standalone services, loopback namespace, no egress/ports/home/data/socket mounts.")


def source_checks():
    errors = []
    count = 0
    for path in source_files():
        if not path.is_file():
            continue
        content = path.read_bytes()
        if path.suffix == ".py":
            compile(content, str(path), "exec", dont_inherit=True)
            count += 1
        if path.suffix == ".sh":
            subprocess.run(["sh", "-n", str(path)], check=True)
        if b"\0" in content:
            continue
        for number, line in enumerate(content.splitlines(), 1):
            trailing = line[len(line.rstrip(b" \t")) :]
            # Existing Markdown hard breaks are intentional prose formatting.
            if trailing and not (path.suffix == ".md" and trailing == b"  " and line.rstrip()):
                errors.append(f"{path.relative_to(ROOT)}:{number}: trailing whitespace")
    if errors:
        raise ValueError("\n".join(errors))
    print(f"PASS: parsed {count} Python sources; whitespace checked tracked and untracked files.")


def run_check(name, command):
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    output = result.stdout + result.stderr
    (OUTPUT / f"{name}.log").write_text(output)
    print(f"{name}: {'PASS' if result.returncode == 0 else 'FAIL'}")
    if result.returncode:
        print(output)
    return {
        "name": name,
        "command": command,
        "exit_code": result.returncode,
        "duration_seconds": round(time.monotonic() - start, 3),
    }


def checks(mode):
    start = time.monotonic()
    results = []
    for name, operation in [("isolation", isolation), ("syntax-whitespace", source_checks)]:
        try:
            operation()
            results.append({"name": name, "exit_code": 0})
        except (ValueError, SyntaxError, OSError) as exc:
            print(f"FAIL {name}: {exc}")
            results.append({"name": name, "exit_code": 1, "error": str(exc)})
            if name == "isolation":
                return 1
    (OUTPUT / "source-hashes.json").write_text(json.dumps(source_hashes(), indent=2))
    commands = [
        ("ruff-lint", ["ruff", "check", "--no-cache", "--config", CONFIG, "twin_lab", "tests"]),
        (
            "ruff-format",
            ["ruff", "format", "--check", "--no-cache", "--config", CONFIG, "twin_lab", "tests"],
        ),
        ("mypy", ["mypy", "--config-file", CONFIG]),
        ("guard-self-tests", ["python", "tests/quality/check_guards.py"]),
        ("unit-fast", ["python", "tests/quality/run_unittest.py", "fast"]),
    ]
    if mode == "--full":
        commands.extend(
            (f"unit-{group}", ["python", "tests/quality/run_unittest.py", group])
            for group in ("compatibility", "sequences", "interruptions")
        )
    results.extend(run_check(name, command) for name, command in commands)
    versions = {
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        **{name: importlib.metadata.version(name) for name in ("ruff", "mypy")},
    }
    (OUTPUT / "python-results.json").write_text(
        json.dumps(
            {
                "checks": results,
                "versions": versions,
                "duration_seconds": round(time.monotonic() - start, 3),
            },
            indent=2,
        )
    )
    return int(any(check["exit_code"] for check in results))


def required_stages(mode):
    names = ["isolation", "git-exclusion", "python", "javascript"]
    return names + (["server-start", "browser"] if mode == "--full" else [])


def evidence_errors(result):
    mode = result["mode"]
    errors = []
    stages = result["host_checks"]
    if [stage["name"] for stage in stages] != required_stages(mode):
        errors.append("required host stage missing, repeated or out of order")
    python_names = [
        "isolation",
        "syntax-whitespace",
        "ruff-lint",
        "ruff-format",
        "mypy",
        "guard-self-tests",
        "unit-fast",
    ]
    groups = ["fast"]
    if mode == "--full":
        groups += ["compatibility", "sequences", "interruptions"]
        python_names += [f"unit-{group}" for group in groups[1:]]
    python_checks = result["reports"].get("python", {}).get("checks", [])
    if [check["name"] for check in python_checks] != python_names or any(
        check["exit_code"] for check in python_checks
    ):
        errors.append("required Python checks missing or failed")
    js_checks = result["reports"].get("javascript", {}).get("checks", [])
    js_names = {check["name"] for check in js_checks}
    expected_js = {"typescript", "guard:JavaScript syntax", "guard:JavaScript type mismatch"}
    for directory in (ROOT / "twin_lab/static", ROOT / "tests"):
        expected_js.update(
            f"syntax:{path}"
            for path in directory.rglob("*")
            if path.suffix in {".js", ".mjs", ".cjs"}
        )
    if (
        js_names != expected_js
        or len(js_names) != len(js_checks)
        or any(check["exit_code"] for check in js_checks)
    ):
        errors.append("required JavaScript checks missing or failed")
    for group in groups:
        report = result["reports"].get(group, {})
        if not report.get("count") or report.get("count") != len(report.get("test_ids", [])):
            errors.append(f"required {group} tests missing or not executed")
        if any(
            report.get(key)
            for key in (
                "failures",
                "errors",
                "skipped",
                "unexpected_successes",
                "expected_failures",
            )
        ):
            errors.append(f"{group} tests failed or skipped")
    return errors


def summary():
    mode = (OUTPUT / "mode.txt").read_text().strip()
    result = {
        "mode": mode,
        "source_head": (OUTPUT / "source-head.txt").read_text().strip(),
        "host_checks": [],
        "reports": {},
        "missing": [],
    }
    for line in (OUTPUT / "host-checks.tsv").read_text().splitlines():
        name, code = line.split("\t")
        result["host_checks"].append({"name": name, "exit_code": int(code)})
    required = ["python", "javascript", "fast"]
    if mode == "--full":
        required += ["browser", "compatibility", "sequences", "interruptions"]
    for name in required:
        path = OUTPUT / f"{name}-results.json"
        if path.exists():
            result["reports"][name] = json.loads(path.read_text())
        else:
            result["missing"].append(name)
    before = (
        json.loads((OUTPUT / "source-hashes.json").read_text())
        if (OUTPUT / "source-hashes.json").exists()
        else {}
    )
    initial_inventory = (OUTPUT / "source-files.bin").read_bytes()
    final_inventory = (OUTPUT / "source-files-after.bin").read_bytes()
    result["source_changed_during_run"] = (
        before != source_hashes() or initial_inventory != final_inventory
    )
    result["evidence_errors"] = evidence_errors(result)
    browser = result["reports"].get("browser", {})
    browser_stats = browser.get("stats", {})
    invalid_browser = mode == "--full" and (
        not browser_stats.get("expected")
        or any(browser_stats.get(key, 0) for key in ("unexpected", "flaky", "skipped"))
    )
    failed = (
        any(check["exit_code"] for check in result["host_checks"])
        or result["missing"]
        or result["source_changed_during_run"]
        or invalid_browser
        or result["evidence_errors"]
    )
    result["status"] = "FAIL" if failed else "PASS"
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2))
    print(
        f"{result['status']} {mode}: {len(result['host_checks'])} required host stages; missing={result['missing']}"
    )
    if result["source_changed_during_run"]:
        print("FAIL: source changed during this run; repeat against a stable source snapshot.")
    for error in result["evidence_errors"]:
        print(f"FAIL: {error}")
    return int(bool(failed))


if __name__ == "__main__":
    if sys.argv[1] == "--isolation":
        isolation()
        raise SystemExit(0)
    raise SystemExit(summary() if sys.argv[1] == "--summary" else checks(sys.argv[1]))

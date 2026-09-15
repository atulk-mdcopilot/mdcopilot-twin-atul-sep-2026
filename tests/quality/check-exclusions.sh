#!/bin/sh
# Verify the real ignore checker and prove a deliberately exposed sentinel fails.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
sh "$root/tests/check-git-ignore.sh"
scratch=$(mktemp -d "${TMPDIR:-/tmp}/twin-quality-ignore-negative.XXXXXX")
trap 'rm -rf -- "$scratch"' EXIT HUP INT TERM
mkdir -p "$scratch/tests" "$scratch/fixtures"
cp "$root/tests/check-git-ignore.sh" "$scratch/tests/check-git-ignore.sh"
cp "$root/fixtures/cases.json" "$scratch/fixtures/cases.json"
cp "$root/.gitignore" "$scratch/.gitignore"
printf '\n!credentials.json\n' >> "$scratch/.gitignore"
if sh "$scratch/tests/check-git-ignore.sh" > "$scratch/result.txt" 2>&1; then
  printf '%s\n' 'FAIL: deliberately exposed credentials sentinel was not rejected.' >&2
  exit 1
fi
if ! grep -q 'credentials.json' "$scratch/result.txt"; then
  cat "$scratch/result.txt" >&2
  printf '%s\n' 'FAIL: negative check failed for an unexpected reason.' >&2
  exit 1
fi
printf '%s\n' 'PASS: deliberately exposed credentials sentinel rejected in an isolated repository.'

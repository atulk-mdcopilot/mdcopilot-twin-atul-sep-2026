#!/bin/sh
# Git housekeeping only: use synthetic sentinels and an isolated temporary index.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
scratch=$(mktemp -d "${TMPDIR:-/tmp}/twin-lab-ignore.XXXXXX")
trap 'rm -rf -- "$scratch"' EXIT HUP INT TERM

# Do not inherit Git environment overrides that could target the real checkout.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
cp "$root/.gitignore" "$scratch/.gitignore"
mkdir -p "$scratch/fixtures" "$scratch/data" "$scratch/runtime" \
  "$scratch/exports" "$scratch/backups" "$scratch/logs" "$scratch/nested" \
  "$scratch/governance-private" "$scratch/permission-receipts" "$scratch/lifecycle-ledger"
mkdir -p "$scratch/quality-output" "$scratch/test-results" "$scratch/playwright-report" \
  "$scratch/node_modules" "$scratch/.mypy_cache" "$scratch/.ruff_cache"
cp "$root/fixtures/cases.json" "$scratch/fixtures/cases.json"

checked=0
for path in \
  data/responses.json runtime/presentations.json exports/download.json \
  backups/observations.json logs/server-output.txt \
  observations.db observations.db-wal observations.db-shm \
  observations.sqlite observations.sqlite-wal observations.sqlite-journal \
  observations.sqlite3 observations.sqlite3-wal observations.sqlite3-shm \
  twin-lab-export.json dated-twin-lab-export-2026.json twin-lab-responses.json \
  observations.jsonl server.log .env .env.local .env.production \
  client.pem private.key credentials.json secrets.toml \
  nested/observations.sqlite3 nested/.env nested/credentials.json \
  nested/twin-lab-export.json \
  governance-private/owners.json permission-receipts/receipt.json \
  lifecycle-ledger/ledger.txt twin-lab-permission-test.json \
  twin-lab-governance-test.json twin-lab-disposal-plan.json \
  deletion-ledger.json lifecycle-events.jsonl before-governance-verification.json \
  twin-lab-export-00000000-0000-0000-0000-000000000000.json \
  quality-output/results.json test-results/trace.zip playwright-report/index.html \
  node_modules/package.js .mypy_cache/cache.json .ruff_cache/cache.json checker.tsbuildinfo
do
  printf '%s\n' 'Synthetic sentinel only; no response data or credentials.' > "$scratch/$path"
  checked=$((checked + 1))
done

git -c core.excludesFile=/dev/null init -q "$scratch"
git -C "$scratch" -c core.excludesFile=/dev/null add .
staged=$(git -C "$scratch" ls-files)
expected='.gitignore
fixtures/cases.json'
if [ "$staged" != "$expected" ]; then
  printf '%s\n' 'FAIL: normal git add staged unexpected files in the isolated repository:' >&2
  printf '%s\n' "$staged" >&2
  exit 1
fi
printf 'PASS: %s runtime/credential sentinels excluded; only .gitignore and synthetic fixtures staged in the isolated repository.\n' "$checked"

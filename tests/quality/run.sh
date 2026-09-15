#!/bin/sh
# Host work is orchestration and Git metadata only; all code/tools run in Docker.
set -eu
mode=${1:---fast}
case "$mode" in --fast|--full) ;; *) printf 'Usage: sh tests/quality/run.sh [--fast|--full]\n' >&2; exit 2 ;; esac
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
# Fixed temporary parent prevents a caller's TMPDIR from targeting actual data.
TWIN_QUALITY_OUTPUT=$(mktemp -d /tmp/twin-lab-quality.XXXXXX)
export TWIN_QUALITY_OUTPUT
project="twin-quality-$(basename "$TWIN_QUALITY_OUTPUT" | tr '[:upper:].' '[:lower:]-')"
compose="$root/tests/quality/compose.yaml"
cd "$root" || exit 2
printf 'Quality artifacts: %s\n' "$TWIN_QUALITY_OUTPUT"
printf '%s\n' "$root" > "$TWIN_QUALITY_OUTPUT/source-root.txt"
printf '%s\n' "$mode" > "$TWIN_QUALITY_OUTPUT/mode.txt"
: > "$TWIN_QUALITY_OUTPUT/host-checks.tsv"
cleanup() {
  docker compose -p "$project" -f "$compose" down --remove-orphans > "$TWIN_QUALITY_OUTPUT/cleanup.log" 2>&1
}
trap cleanup EXIT HUP INT TERM
step() {
  name=$1
  shift
  printf '\nChecking %s\n' "$name"
  if "$@" > "$TWIN_QUALITY_OUTPUT/$name.log" 2>&1; then code=0; else code=$?; fi
  last_code=$code
  cat "$TWIN_QUALITY_OUTPUT/$name.log"
  printf '%s\t%s\n' "$name" "$code" >> "$TWIN_QUALITY_OUTPUT/host-checks.tsv"
  return 0
}
# Never inherit index overrides or operate on the user's real index.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
for required in twin-lab-quality-python:1 twin-lab-quality-browser:1; do
  if ! docker image inspect "$required" > /dev/null 2>&1; then
    printf 'FAIL: missing required image %s. Run the separately approved tests/quality/setup.sh --approved.\n' "$required" >&2
    exit 2
  fi
done
docker image inspect twin-lab-quality-python:1 twin-lab-quality-browser:1 > "$TWIN_QUALITY_OUTPUT/tool-images.json"
git rev-parse HEAD > "$TWIN_QUALITY_OUTPUT/source-head.txt"
git ls-files --cached --others --exclude-standard --deduplicate -z > "$TWIN_QUALITY_OUTPUT/source-files.bin"
docker compose -p "$project" -f "$compose" config --format json > "$TWIN_QUALITY_OUTPUT/compose-resolved.json"
step isolation docker run --rm --network none --read-only --tmpfs /tmp \
  --mount "type=bind,src=$root,dst=/app,readonly" \
  --mount "type=bind,src=$TWIN_QUALITY_OUTPUT,dst=/quality-output" \
  --workdir /app python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 \
  python tests/quality/check_python.py --isolation
if [ "$last_code" -ne 0 ]; then
  printf '%s\n' 'FAIL: isolation verification rejected the configuration; no application tests were started.' >&2
  exit 2
fi
step git-exclusion sh tests/quality/check-exclusions.sh
step python docker compose -p "$project" -f "$compose" run --rm --no-deps python-checks python tests/quality/check_python.py "$mode"
step javascript docker compose -p "$project" -f "$compose" run --rm --no-deps js-checks node tests/quality/check-js.cjs
if [ "$mode" = --full ]; then
  step server-start docker compose -p "$project" -f "$compose" up --detach --wait --no-build --pull never test-server
  step browser docker compose -p "$project" -f "$compose" run --rm --no-deps browser-checks node /opt/twin-quality/node_modules/@playwright/test/cli.js test --config /app/tests/browser/playwright.config.cjs
fi
git ls-files --cached --others --exclude-standard --deduplicate -z > "$TWIN_QUALITY_OUTPUT/source-files-after.bin"
docker compose -p "$project" -f "$compose" run --rm --no-deps python-checks python tests/quality/check_python.py --summary
exit $?

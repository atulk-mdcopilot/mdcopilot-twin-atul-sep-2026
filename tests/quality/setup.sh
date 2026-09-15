#!/bin/sh
# Explicit, network-enabled setup only. run.sh never downloads or installs tools.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
case "${1:-}" in
  --approved) ;;
  *) printf '%s\n' 'After authorizing test-only dependency downloads, run: sh tests/quality/setup.sh --approved' >&2; exit 2 ;;
esac
docker build --pull=false --file "$root/tests/quality/Dockerfile.python" --tag twin-lab-quality-python:1 "$root/tests/quality"
docker build --pull=false --file "$root/tests/quality/Dockerfile.browser" --tag twin-lab-quality-browser:1 "$root/tests/quality"
printf '%s\n' 'Test images ready. Test execution uses isolated, offline containers.'

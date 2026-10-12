#!/usr/bin/env bash
set -euo pipefail

mode=${1:-}
[[ -z "$mode" || "$mode" == "--check" ]] || {
  echo "usage: scripts/generate_openapi.sh [--check]" >&2
  exit 2
}

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$root"
mkdir -p contracts .cache/temp
generated=$(mktemp ".cache/temp/m1-openapi.XXXXXX")
trap 'rm -f -- "$generated"' EXIT

if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -B .cache/generate_openapi.py >"$generated"
else
  runtime=${M1_CONTAINER_CLI:-podman}
  image=${M1_OPENAPI_IMAGE:-localhost/industrial-ops/m1-api:local}
  "$runtime" run --rm \
    --volume "$root:/workspace:ro" \
    --workdir /workspace \
    --env PYTHONPATH=/workspace/src \
    "$image" python -B .cache/generate_openapi.py >"$generated"
fi

if [[ "$mode" == "--check" ]]; then
  cmp -s "$generated" contracts/openapi.json || {
    echo "OpenAPI contract drift: run scripts/generate_openapi.sh" >&2
    exit 1
  }
else
  mv -f -- "$generated" contracts/openapi.json
fi

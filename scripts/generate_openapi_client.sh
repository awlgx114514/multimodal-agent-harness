#!/usr/bin/env bash
set -euo pipefail

mode=${1:-}
[[ -z "$mode" || "$mode" == "--check" ]] || {
  echo "usage: scripts/generate_openapi_client.sh [--check]" >&2
  exit 2
}
[[ -x web/node_modules/.bin/openapi-typescript ]] || {
  echo "web dependencies are not installed" >&2
  exit 3
}

mkdir -p web/generated/api .cache/temp
generated=$(mktemp ".cache/temp/m1-openapi-client.XXXXXX")
trap 'rm -f -- "$generated"' EXIT
if [[ -x web/node_modules/.bin/openapi-typescript ]]; then
  web/node_modules/.bin/openapi-typescript contracts/openapi.json -o "$generated" >/dev/null
elif command -v node >/dev/null 2>&1; then
  node web/node_modules/openapi-typescript/bin/cli.js \
    contracts/openapi.json -o "$generated" >/dev/null
elif [[ -n "${M1_NODE_EXECUTABLE:-}" ]]; then
  "$M1_NODE_EXECUTABLE" web/node_modules/openapi-typescript/bin/cli.js \
    contracts/openapi.json -o "$generated" >/dev/null
else
  echo "Node.js is required to generate the API client" >&2
  exit 3
fi

if [[ "$mode" == "--check" ]]; then
  cmp -s "$generated" web/generated/api/schema.d.ts || {
    echo "Generated API client drift: run scripts/generate_openapi_client.sh" >&2
    exit 1
  }
else
  mv -f -- "$generated" web/generated/api/schema.d.ts
fi

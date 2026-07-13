#!/usr/bin/env bash
# Create isolated test fixtures before feature testing (stations, manifest).
#
# Usage:
#   scripts/test_data_prep.sh <slug> [--stg|--url URL]
#
# Writes manifest to projects/<slug>/.test-data/manifest.json
# See skill qa-test-data and projects/<slug>/test-data.md
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"
[[ -z "$SLUG" ]] && { echo "Usage: test_data_prep.sh <slug> [--stg|--url URL]" >&2; exit 1; }
shift

USE_STG=""
BASE_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stg) USE_STG=1; shift ;;
    --url) BASE_URL="${2:-}"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

AUTODIR="$ROOT/projects/$SLUG/automation"
[[ -d "$AUTODIR" ]] || { echo "No automation dir: $AUTODIR" >&2; exit 1; }

ENVF="$ROOT/projects/$SLUG/.secrets/server.env"
if [[ -f "$ENVF" ]]; then
  # shellcheck disable=SC1090
  set -a; . "$ENVF"; set +a
fi

if [[ -n "$USE_STG" ]]; then
  BASE_URL="${STG_URL:-}"
  [[ -n "$BASE_URL" ]] || { echo "STG_URL not set in $ENVF" >&2; exit 1; }
elif [[ -z "$BASE_URL" ]]; then
  BASE_URL="${SERVER_URL:-http://localhost:3000}"
fi

if [[ ! -d "$AUTODIR/node_modules/@playwright/test" ]]; then
  echo "Installing Playwright in $AUTODIR ..."
  ( cd "$AUTODIR" && npm install --no-audit --no-fund --silent ) || exit 1
  ( cd "$AUTODIR" && npx playwright install chromium ) || exit 1
fi

SPEC="specs/test-data-prep.spec.js"
[[ -f "$AUTODIR/$SPEC" ]] || { echo "Prep spec not found: $AUTODIR/$SPEC" >&2; exit 1; }

echo "Test data PREP @ $BASE_URL"
( cd "$AUTODIR" && BASE_URL="$BASE_URL" SERVER_URL="$BASE_URL" npx playwright test "$SPEC" --workers=1 )

MANIFEST="$ROOT/projects/$SLUG/.test-data/manifest.json"
if [[ -f "$MANIFEST" ]]; then
  echo "Manifest: $MANIFEST"
  cat "$MANIFEST"
else
  echo "WARN: manifest not written — check prep spec output" >&2
  exit 1
fi

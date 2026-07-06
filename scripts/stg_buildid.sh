#!/usr/bin/env bash
# STG buildId gate for L5 auto-accept. Reads the LIVE deployed buildId from
# the STG /api/health endpoint so the QA loop only auto-accepts a ticket to Done when
# STG actually serves the expected merge commit (STG can lag main).
#
# Config: projects/<slug>/.secrets/server.env
#   STG_URL=http://<stg-host>            # base URL of the deployed STG app
#   STG_HEALTH_PATH=/api/health          # optional (default /api/health)
#
# Usage:
#   scripts/stg_buildid.sh <slug>                  # print the live STG buildId
#   scripts/stg_buildid.sh <slug> <expected-sha>   # gate: exit 0 if buildId matches, 2 if mismatch
#
# Match is prefix-based (short vs long sha), case-insensitive. Exit 3 if STG_URL unset,
# 4 if health unreachable/no buildId.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"; EXPECT="${2:-}"
[[ -z "$SLUG" ]] && { echo "Usage: stg_buildid.sh <slug> [expected-sha]" >&2; exit 1; }

ENVF="$ROOT/projects/$SLUG/.secrets/server.env"
[[ -f "$ENVF" ]] || { echo "Missing $ENVF" >&2; exit 1; }
# shellcheck disable=SC1090
set -a; . "$ENVF"; set +a

[[ -n "${STG_URL:-}" ]] || { echo "STG_URL not set in $ENVF — cannot run STG buildId gate" >&2; exit 3; }
URL="${STG_URL%/}${STG_HEALTH_PATH:-/api/health}"

JSON="$(curl -fsS -m 15 "$URL" 2>/dev/null)" || { echo "STG health unreachable: $URL" >&2; exit 4; }
BUILD="$(printf '%s' "$JSON" | sed -nE 's/.*"buildId"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p')"
[[ -n "$BUILD" ]] || { echo "no buildId in STG health response" >&2; exit 4; }

if [[ -z "$EXPECT" ]]; then
  echo "$BUILD"
  exit 0
fi

# Normalize + prefix-compare (short sha vs long sha, either direction).
b="$(printf '%s' "$BUILD" | tr 'A-Z' 'a-z')"
e="$(printf '%s' "$EXPECT" | tr 'A-Z' 'a-z')"
if [[ "$b" == "$e"* || "$e" == "$b"* ]]; then
  echo "MATCH live=$BUILD expected=$EXPECT"
  exit 0
else
  echo "MISMATCH live=$BUILD expected=$EXPECT"
  exit 2
fi

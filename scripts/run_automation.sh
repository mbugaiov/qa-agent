#!/usr/bin/env bash
# Run project Playwright specs against local app (via server_ctl) or STG/explicit URL.
#
# Usage:
#   scripts/run_automation.sh <slug>                    # local: sync + up + test + down
#   scripts/run_automation.sh <slug> --stg              # STG (no local server)
#   scripts/run_automation.sh <slug> --url http://host  # explicit base URL
#   scripts/run_automation.sh <slug> --suite all        # all specs (default)
#   scripts/run_automation.sh <slug> --suite <file>     # single spec file under specs/
#
# Requires: npm install in projects/<slug>/automation/ (once).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"
[[ -z "$SLUG" ]] && { echo "Usage: run_automation.sh <slug> [--stg|--url URL] [--suite all|<spec-file>]" >&2; exit 1; }
shift

SUITE="all"
USE_STG=""
BASE_URL=""
MANAGE_SERVER=1
SERVER_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stg) USE_STG=1; MANAGE_SERVER=0; shift ;;
    --url) BASE_URL="${2:-}"; MANAGE_SERVER=0; shift 2 ;;
    --suite) SUITE="${2:-all}"; shift 2 ;;
    --no-server) MANAGE_SERVER=0; shift ;;
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

STARTED=0
cleanup() {
  if [[ "$STARTED" -eq 1 ]]; then
    "$SCRIPT_DIR/server_ctl.sh" "$SLUG" down >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "$MANAGE_SERVER" -eq 1 && -n "${SERVER_URL:-}" && "$BASE_URL" == "$SERVER_URL" ]]; then
  "$SCRIPT_DIR/server_ctl.sh" "$SLUG" sync
  if ! "$SCRIPT_DIR/server_ctl.sh" "$SLUG" status 2>&1 | grep -qi up; then
    "$SCRIPT_DIR/server_ctl.sh" "$SLUG" up || exit 1
    STARTED=1
  fi
fi

if [[ ! -d "$AUTODIR/node_modules/@playwright/test" ]]; then
  echo "Installing Playwright in $AUTODIR ..."
  ( cd "$AUTODIR" && npm install --no-audit --no-fund --silent ) || exit 1
  ( cd "$AUTODIR" && npx playwright install chromium ) || exit 1
fi

SPEC_ARG=""
if [[ "$SUITE" != "all" ]]; then
  SPEC_ARG="specs/$SUITE"
  [[ -f "$AUTODIR/$SPEC_ARG" ]] || { echo "Spec not found: $AUTODIR/$SPEC_ARG" >&2; exit 1; }
fi

echo "Running automation @ $BASE_URL (suite=$SUITE)"
( cd "$AUTODIR" && BASE_URL="$BASE_URL" SERVER_URL="$BASE_URL" npx playwright test ${SPEC_ARG:+$SPEC_ARG} --workers=1 )

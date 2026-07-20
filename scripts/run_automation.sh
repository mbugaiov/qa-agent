#!/usr/bin/env bash
# Run project Playwright specs against local app (via server_ctl) or STG/explicit URL.
#
# Usage:
#   scripts/run_automation.sh <slug>                    # local: sync + up + test + down
#   scripts/run_automation.sh <slug> --stg              # STG (no local server)
#   scripts/run_automation.sh <slug> --url http://host  # explicit base URL
#   scripts/run_automation.sh <slug> --no-server        # skip local server autostart
#   scripts/run_automation.sh <slug> --suite all        # all specs (default)
#   scripts/run_automation.sh <slug> --suite <file>     # single spec file under specs/
#   scripts/run_automation.sh <slug> --prep             # opt-in test-data prep (skipped if prep spec missing)
#   scripts/run_automation.sh <slug> --stg --prep       # prep then run all specs on STG
#
# Requires: npm install in projects/<slug>/automation/ (once).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"
[[ -z "$SLUG" ]] && { echo "Usage: run_automation.sh <slug> [--stg|--url URL] [--suite all|<spec-file>] [--prep]" >&2; exit 1; }
shift

SUITE="all"
USE_STG=""
BASE_URL=""
MANAGE_SERVER=1
SERVER_URL=""
RUN_PREP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stg) USE_STG=1; MANAGE_SERVER=0; shift ;;
    --url) BASE_URL="${2:-}"; MANAGE_SERVER=0; shift 2 ;;
    --suite) SUITE="${2:-all}"; shift 2 ;;
    --no-server) MANAGE_SERVER=0; shift ;;
    --prep) RUN_PREP=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

AUTODIR="$ROOT/projects/$SLUG/automation"
[[ -d "$AUTODIR" ]] || { echo "No automation dir: $AUTODIR" >&2; exit 1; }

PROJECT_YAML="$ROOT/projects/$SLUG/project.yaml"
SERVER_MANAGE=0
if [[ -f "$PROJECT_YAML" ]] && grep -A3 '^server:' "$PROJECT_YAML" | grep -q 'manage:[[:space:]]*true'; then
  SERVER_MANAGE=1
fi

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

if [[ "$MANAGE_SERVER" -eq 1 && "$SERVER_MANAGE" -eq 1 && -n "${SERVER_URL:-}" && "$BASE_URL" == "$SERVER_URL" ]]; then
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

# Prep is opt-in (--prep only). Projects without specs/test-data-prep.spec.js must not fail bare --stg.
if [[ "$RUN_PREP" -eq 1 ]]; then
  PREP_SPEC="$AUTODIR/specs/test-data-prep.spec.js"
  if [[ ! -f "$PREP_SPEC" ]]; then
    echo "Skipping prep: no $PREP_SPEC (add the spec or omit --prep)" >&2
  else
    PREP_ARGS=()
    [[ -n "$USE_STG" ]] && PREP_ARGS+=(--stg)
    [[ -n "$BASE_URL" && -z "$USE_STG" ]] && PREP_ARGS+=(--url "$BASE_URL")
    echo "Running test data prep before automation ..."
    "$SCRIPT_DIR/test_data_prep.sh" "$SLUG" "${PREP_ARGS[@]}" || exit 1
  fi
fi

SPEC_ARG=""
if [[ "$SUITE" != "all" ]]; then
  SPEC_ARG="specs/$SUITE"
  [[ -f "$AUTODIR/$SPEC_ARG" ]] || { echo "Spec not found: $AUTODIR/$SPEC_ARG" >&2; exit 1; }
else
  SPEC_ARG="specs/admin-flows.spec.js specs/primary-flows.spec.js specs/public-surfaces.spec.js specs/rbac-guards.spec.js specs/lab-power.spec.js specs/lab-power-value.spec.js specs/health-nav.spec.js specs/reports-smoke.spec.js specs/landing.spec.js specs/stations-filter.spec.js specs/theme.spec.js specs/queue-triage.spec.js specs/equipment-picker.spec.js specs/stations-drilldown.spec.js specs/scheduled-backlog.spec.js specs/enhanced-reporting.spec.js specs/display-pii.spec.js specs/schedule-slot.spec.js specs/station-schedule-visibility.spec.js specs/equipment-guard.spec.js specs/capability-matching.spec.js specs/qa-regressions.spec.js specs/nav-consolidated.spec.js specs/edit-submitted.spec.js specs/quick-test-guardrails.spec.js"
fi

echo "Running automation @ $BASE_URL (suite=$SUITE)"
( cd "$AUTODIR" && BASE_URL="$BASE_URL" SERVER_URL="$BASE_URL" npx playwright test ${SPEC_ARG:+$SPEC_ARG} --workers=1 )

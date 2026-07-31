#!/usr/bin/env bash
# Smoke-test QA factory tick notification delivery.
# Usage: bash scripts/test_tick_notify.sh <slug> [--idle]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:-}"
if [[ -z "$SLUG" ]]; then
  echo "Usage: test_tick_notify.sh <slug> [--idle]" >&2
  exit 2
fi
shift || true
EXTRA=()
if [[ "${1:-}" == "--idle" ]]; then
  EXTRA=(--idle)
fi
exec python3 "$ROOT/scripts/qa_tick_notify.py" --slug "$SLUG" --project "$ROOT/projects/$SLUG" --smoke ${EXTRA[@]+"${EXTRA[@]}"}

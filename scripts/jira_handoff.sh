#!/usr/bin/env bash
# Read dev handoff on a Jira ticket before V/T retest (ADF comments → plain text).
#
# Usage:
#   scripts/jira_handoff.sh <slug> <JIRA-KEY> [--log] [--json]
#
# --log  Append handoff_read to factory ledger (required before dod_check when scope non-empty).
# --json Machine-readable output.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"
KEY="${2:-}"
[[ -z "$SLUG" || -z "$KEY" ]] && {
  echo "Usage: jira_handoff.sh <slug> <JIRA-KEY> [--log] [--json]" >&2
  exit 1
}
shift 2

LOG=""
JSON=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --log) LOG=1 ;;
    --json) JSON=1 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

PY_ARGS=(--project "$ROOT/projects/$SLUG" --key "$KEY")
[[ -n "$LOG" ]] && PY_ARGS+=(--log)
[[ -n "$JSON" ]] && PY_ARGS+=(--json)

python3 "$SCRIPT_DIR/jira_handoff.py" "${PY_ARGS[@]}"

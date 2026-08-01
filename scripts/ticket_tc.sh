#!/usr/bin/env bash
# Link a Jira scope ticket to a persisted regression TC under test-cases/.
#
# Usage:
#   scripts/ticket_tc.sh <slug> <TICKET> --title "…" [--steps-file path] [--expected "…"] [--scenario SC-*] [--req REQ-*] [--log]
#   scripts/ticket_tc.sh <slug> <TICKET> --link TC-<id> [--log]
#
# Run after jira_handoff + openspec_read, before browser retest (skill qa-loop).
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"
TICKET="${2:-}"
[[ -z "$SLUG" || -z "$TICKET" ]] && {
  echo "Usage: ticket_tc.sh <slug> <TICKET> [--title …] [--link TC-id] [--steps-file path] [--expected …] [--log]" >&2
  exit 1
}
shift 2
exec python3 "$SCRIPT_DIR/ticket_tc.py" --project "$ROOT/projects/$SLUG" --ticket "$TICKET" "$@"

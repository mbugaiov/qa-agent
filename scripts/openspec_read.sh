#!/usr/bin/env bash
# Print OpenSpec excerpts for QA retest planning.
#
# Usage:
#   scripts/openspec_read.sh <slug> --cap <capability> [--grep PATTERN]
#   scripts/openspec_read.sh <slug> --change <change-id> [--cap <capability>] [--grep PATTERN]
#   scripts/openspec_read.sh <slug> --ticket <KEY>   # infer from handoff hints
#
# Reads from SERVER_GIT_WORKTREE (server.env) or SERVER_GIT_SRC_REPO fallback.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:?slug}"; shift
PROJ="$ROOT/projects/$SLUG"
ENVF="$PROJ/.secrets/server.env"
[[ -f "$ENVF" ]] || { echo "No server.env: $ENVF" >&2; exit 1; }
# shellcheck disable=SC1090
set -a; . "$ENVF"; set +a

WT="${SERVER_GIT_WORKTREE:-}"
SRC="${SERVER_GIT_SRC_REPO:-}"
BASE=""
if [[ -n "$WT" && -d "$WT/openspec" ]]; then BASE="$WT"
elif [[ -n "$SRC" && -d "$SRC/openspec" ]]; then BASE="$SRC"
else
  echo "ERROR: no openspec tree (set SERVER_GIT_WORKTREE or SERVER_GIT_SRC_REPO)" >&2
  exit 1
fi

CAP=""; CHANGE=""; TICKET=""; GREP=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cap) CAP="${2:-}"; shift 2 ;;
    --change) CHANGE="${2:-}"; shift 2 ;;
    --ticket) TICKET="${2:-}"; shift 2 ;;
    --grep) GREP="${2:-}"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -n "$TICKET" && -z "$CHANGE" ]]; then
  HINTS="$(python3 "$SCRIPT_DIR/jira_handoff.py" --project "$PROJ" --key "$TICKET" --json 2>/dev/null || true)"
  CHANGE="$(echo "$HINTS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('hints',{}).get('change',''))" 2>/dev/null || true)"
  PR="$(echo "$HINTS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('hints',{}).get('pr',''))" 2>/dev/null || true)"
  echo "=== Ticket $TICKET handoff hints ==="
  echo "PR: ${PR:-unknown}"
  echo "Change: ${CHANGE:-unknown — pass --change explicitly}"
  echo
fi

read_spec() {
  local f="$1"
  [[ -f "$f" ]] || return 1
  echo "────────────────────────────────────────"
  echo "FILE: $f"
  echo "────────────────────────────────────────"
  if [[ -n "$GREP" ]]; then
    rg -n -i "$GREP" "$f" -C 3 2>/dev/null || sed -n '1,120p' "$f"
  else
    sed -n '1,160p' "$f"
    local lines; lines=$(wc -l < "$f" | tr -d ' ')
    [[ "$lines" -gt 160 ]] && echo "… ($lines lines total — use --grep to narrow)"
  fi
  echo
}

REQ_INDEX="$PROJ/requirements/openspec-requirements.md"
if [[ -f "$REQ_INDEX" ]]; then
  echo "=== QA REQ index: $REQ_INDEX ==="
  if [[ -n "$GREP" ]]; then rg -n -i "$GREP" "$REQ_INDEX" -C 1 || true
  else head -40 "$REQ_INDEX"; echo "…"; fi
  echo
fi

if [[ -n "$CHANGE" ]]; then
  DELTA_DIR="$BASE/openspec/changes/$CHANGE/specs"
  if [[ -d "$DELTA_DIR" ]]; then
    echo "=== Change delta: $CHANGE ==="
    if [[ -n "$CAP" ]]; then
      read_spec "$DELTA_DIR/$CAP/spec.md"
    else
      while IFS= read -r -d '' f; do read_spec "$f"; done < <(find "$DELTA_DIR" -name 'spec.md' -print0 | sort -z)
    fi
  else
    echo "WARN: no delta at $DELTA_DIR" >&2
  fi
fi

if [[ -n "$CAP" ]]; then
  read_spec "$BASE/openspec/specs/$CAP/spec.md"
else
  echo "Tip: pass --cap <capability> or --grep <pattern> to narrow output"
fi

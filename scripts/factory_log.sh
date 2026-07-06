#!/usr/bin/env bash
# Append one factory event to projects/<slug>/factory/runs/<ticket>.jsonl
#
# Usage:
#   scripts/factory_log.sh <slug> <ticket> <event> [key=val ...] [--agent qa|dev|cr|system]
#
# Examples:
#   factory_log.sh <slug> _loop tick_start run=<YYYY-MM-DD>-exploratory-<task>
#   factory_log.sh <slug> ABC-123 verdict PASS merge_sha=<sha> --agent qa
#   factory_log.sh <slug> ABC-123 transition to=Done --agent qa
#
# Values: bare words, key=val pairs, or JSON objects (start with {).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SLUG="${1:-}"; TICKET="${2:-}"; EVENT="${3:-}"
[[ -z "$SLUG" || -z "$TICKET" || -z "$EVENT" ]] && {
  echo "Usage: factory_log.sh <slug> <ticket> <event> [key=val ...] [--agent qa|dev|cr|system]" >&2
  exit 1
}
shift 3

AGENT="qa"
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENT="${2:-qa}"; shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

RUNS="$ROOT/projects/$SLUG/factory/runs"
[[ -d "$ROOT/projects/$SLUG" ]] || { echo "No such project: projects/$SLUG" >&2; exit 1; }
mkdir -p "$RUNS"

FILE="$RUNS/${TICKET}.jsonl"
python3 - "$FILE" "$TICKET" "$EVENT" "$AGENT" "${ARGS[@]}" <<'PY'
import json, sys, datetime, pathlib

path, ticket, event, agent = sys.argv[1:5]
extra = sys.argv[5:]

detail = {}
for raw in extra:
    if raw.startswith("{"):
        try:
            detail.update(json.loads(raw))
        except json.JSONDecodeError:
            detail["_raw"] = raw
    elif "=" in raw:
        k, _, v = raw.partition("=")
        detail[k] = v
    else:
        detail[raw] = True

rec = {
    "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "ticket": ticket,
    "event": event,
    "agent": agent,
}
if detail:
    rec["detail"] = detail

p = pathlib.Path(path)
with p.open("a", encoding="utf-8") as f:
    f.write(json.dumps(rec, separators=(",", ":")) + "\n")

print(f"logged {event} -> {path}")
PY

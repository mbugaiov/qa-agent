#!/usr/bin/env bash
# Gate: per-ticket machine DoD before qa-loop tick_end.
#
# Reads factory ledger since the latest tick_start. Every scope ticket must have
# a dod_check event with a terminal verdict (DONE, FAIL, RETURN_DEV, SKIP_DEV).
# PARTIAL, DEFERRED, PASS_PENDING, and BLOCKED are rejected — finish DoD, FAIL, or RETURN_DEV.
#
# Usage:
#   scripts/factory_tick_gate.sh <slug> [--keys RQ-1,RQ-2,...]
#
# If --keys omitted, uses the latest scope_check event in the current tick.
# Exit 0 = gate open (safe to log tick_end). Exit 1 = gate closed (list gaps).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"
shift || true

KEYS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keys) KEYS="${2:-}"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -z "$SLUG" ]] && {
  echo "Usage: factory_tick_gate.sh <slug> [--keys RQ-1,RQ-2,...]" >&2
  exit 1
}

RUNS="$ROOT/projects/$SLUG/factory/runs"
[[ -d "$ROOT/projects/$SLUG" ]] || { echo "GATE CLOSED: no project projects/$SLUG" >&2; exit 1; }

python3 - "$RUNS" "$KEYS" <<'PY'
import json, sys, pathlib

runs_dir = pathlib.Path(sys.argv[1])
keys_arg = sys.argv[2].strip() if len(sys.argv) > 2 else ""

def load_events(path):
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out

loop_events = load_events(runs_dir / "_loop.jsonl")

tick_start_ts = None
for ev in reversed(loop_events):
    if ev.get("event") == "tick_start":
        tick_start_ts = ev.get("ts")
        break

if not tick_start_ts:
    print("GATE CLOSED: no tick_start in ledger — log tick_start first", file=sys.stderr)
    sys.exit(1)

def since_tick(ev):
    return (ev.get("ts") or "") >= tick_start_ts

scope_keys = []
scope_count = 0
if keys_arg:
    scope_keys = [k.strip() for k in keys_arg.split(",") if k.strip()]
    scope_count = len(scope_keys)
else:
    for ev in reversed(loop_events):
        if not since_tick(ev):
            break
        if ev.get("event") == "scope_check":
            d = ev.get("detail") or {}
            scope_keys = d.get("keys") or []
            if isinstance(scope_keys, str):
                scope_keys = [k.strip() for k in scope_keys.split(",") if k.strip()]
            try:
                scope_count = int(d.get("count", len(scope_keys)))
            except (TypeError, ValueError):
                scope_count = len(scope_keys)
            break

if not scope_keys:
    print("GATE CLOSED: no scope keys — log scope_check or pass --keys", file=sys.stderr)
    sys.exit(1)

TERMINAL = {"DONE", "FAIL", "RETURN_DEV", "SKIP_DEV"}
FORBIDDEN = {"PARTIAL", "DEFERRED", "PASS_PENDING", "BLOCKED"}
errors = []

def ticket_has_event(key, event_name):
    return any(ev.get("event") == event_name for ev in load_events(runs_dir / f"{key}.jsonl") if since_tick(ev))

def ticket_dod_verdict(key):
    for ev in reversed([ev for ev in load_events(runs_dir / f"{key}.jsonl") if since_tick(ev)]):
        if ev.get("event") == "dod_check":
            return str((ev.get("detail") or {}).get("verdict", "")).upper()
    return ""

effective_scope = scope_count if scope_count > 0 else len(scope_keys)
if effective_scope > 0:
    has_exploratory = any(ev.get("event") == "exploratory" for ev in loop_events if since_tick(ev))
    if has_exploratory:
        for key in scope_keys:
            if ticket_dod_verdict(key) not in TERMINAL:
                errors.append(
                    f"exploratory logged before {key} has terminal dod_check — finish scope retest first"
                )
    for key in scope_keys:
        if not ticket_has_event(key, "handoff_read"):
            errors.append(f"{key}: missing handoff_read — run scripts/jira_handoff.sh <slug> {key} --log")

def has_transition(events, target="In Progress"):
    for ev in reversed(events):
        if ev.get("event") == "transition":
            d = ev.get("detail") or {}
            to = str(d.get("to", "")).lower()
            if to.replace("_", " ") == target.lower():
                return True
    return False

checked = {}

for key in scope_keys:
    events = [ev for ev in load_events(runs_dir / f"{key}.jsonl") if since_tick(ev)]
    dod = None
    for ev in reversed(events):
        if ev.get("event") == "dod_check":
            dod = ev.get("detail") or {}
            break
    if not dod:
        errors.append(f"{key}: missing dod_check since tick_start")
        continue

    verdict = str(dod.get("verdict", "")).upper()
    checked[key] = verdict

    if verdict in FORBIDDEN:
        errors.append(f"{key}: verdict {verdict} is not terminal — complete DoD, FAIL, or RETURN_DEV")
        continue
    if verdict not in TERMINAL:
        errors.append(f"{key}: verdict {verdict!r} not in {sorted(TERMINAL)}")
        continue

    if verdict == "FAIL":
        if not dod.get("bug_filed"):
            errors.append(f"{key}: FAIL requires bug_filed=<KEY> (product defect)")
        if not dod.get("openspec_read"):
            errors.append(f"{key}: FAIL requires openspec_read=true (run openspec_read.sh before retest)")
        if not dod.get("dev_handoff"):
            errors.append(f"{key}: FAIL requires dev_handoff=<path> (templates/retest-fail-dev-handoff.md posted to Jira)")
        if not dod.get("retest_attempted"):
            errors.append(f"{key}: FAIL requires retest_attempted=true (feature steps were run)")
        if not dod.get("feature_steps_executed"):
            errors.append(f"{key}: FAIL requires feature_steps_executed=true")
        if not has_transition(events) and not dod.get("transition"):
            errors.append(f"{key}: FAIL requires transition to=In Progress (V/T cannot stay open)")

    if verdict == "RETURN_DEV":
        if not dod.get("bug_filed") and not dod.get("dev_ticket"):
            errors.append(f"{key}: RETURN_DEV requires bug_filed or dev_ticket (separate issue for dev)")
        if not dod.get("openspec_read"):
            errors.append(f"{key}: RETURN_DEV requires openspec_read=true")
        if not dod.get("dev_handoff"):
            errors.append(f"{key}: RETURN_DEV requires dev_handoff=<path>")
        if not dod.get("retest_attempted"):
            errors.append(f"{key}: RETURN_DEV requires retest_attempted=true — smoke alone is not retest")
        if not dod.get("alternate_locators_tried"):
            errors.append(f"{key}: RETURN_DEV requires alternate_locators_tried=true (exhaust data-testid/role/text/native click)")
        if not dod.get("feature_steps_executed") and not dod.get("steps_tried"):
            errors.append(f"{key}: RETURN_DEV requires feature_steps_executed=true or steps_tried=<summary>")
        if not has_transition(events) and not dod.get("transition"):
            errors.append(f"{key}: RETURN_DEV requires transition to=In Progress (never leave V/T blocked)")
        if str(dod.get("jira_status", "")).lower() == "validate/testing" and not (has_transition(events) or dod.get("transition")):
            errors.append(f"{key}: RETURN_DEV — must move ticket off Validate/Testing same tick")

    if verdict == "DONE":
        if not dod.get("two_pass"):
            errors.append(f"{key}: DONE requires two_pass=true")
        if not dod.get("canonical_source"):
            errors.append(f"{key}: DONE requires canonical_source=true")
        if not dod.get("feature_steps_executed"):
            errors.append(f"{key}: DONE requires feature_steps_executed=true")
        gate = str(dod.get("buildid_gate", "")).upper()
        if gate not in ("MATCH", "MATCH_AHEAD", "N/A", "SKIP"):
            errors.append(f"{key}: DONE requires buildid_gate MATCH|MATCH_AHEAD|N/A|SKIP (got {gate!r})")
        if not dod.get("recording_exempt") and not dod.get("recording_attached"):
            errors.append(f"{key}: DONE requires recording_attached=true or recording_exempt=true")

    if verdict == "SKIP_DEV":
        if not dod.get("note"):
            errors.append(f"{key}: SKIP_DEV requires note")
        js = str(dod.get("jira_status", "")).lower()
        if js and js not in ("in progress", "in_progress"):
            errors.append(f"{key}: SKIP_DEV only when jira_status=In Progress (got {js})")

if errors:
    print("GATE CLOSED — tick_end not allowed:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

print(f"GATE OPEN — {len(scope_keys)} scope ticket(s) have terminal dod_check:")
for key in scope_keys:
    print(f"  {key}: {checked.get(key, '?')}")
sys.exit(0)
PY

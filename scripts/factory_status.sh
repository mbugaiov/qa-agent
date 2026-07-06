#!/usr/bin/env bash
# Offline factory ledger summary for a project.
# Reads projects/<slug>/factory/runs/*.jsonl — no network required.
#
# Usage:
#   scripts/factory_status.sh <slug>           # human-readable summary
#   scripts/factory_status.sh <slug> --json    # machine-readable
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"; MODE="${2:-}"
[[ -z "$SLUG" ]] && { echo "Usage: factory_status.sh <slug> [--json]" >&2; exit 1; }

RUNS="$ROOT/projects/$SLUG/factory/runs"
[[ -d "$ROOT/projects/$SLUG" ]] || { echo "No such project: projects/$SLUG" >&2; exit 1; }

python3 - "$RUNS" "$MODE" <<'PY'
import json, sys, pathlib, collections

runs_dir = pathlib.Path(sys.argv[1])
json_mode = len(sys.argv) > 2 and sys.argv[2] == "--json"

if not runs_dir.is_dir():
    out = {"tickets": {}, "loop": {}, "failures": [], "files": 0}
    if json_mode:
        print(json.dumps(out, indent=2))
    else:
        print(f"Factory ledger: {runs_dir} (empty — no events yet)")
    sys.exit(0)

events_by_ticket = collections.defaultdict(list)
loop_events = []

for path in sorted(runs_dir.glob("*.jsonl")):
    key = path.stem
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if key == "_loop":
            loop_events.append(ev)
        else:
            events_by_ticket[key].append(ev)

failures = []
summaries = {}
for ticket, evs in events_by_ticket.items():
    last = evs[-1]
    last_verdict = None
    for ev in reversed(evs):
        if ev.get("event") == "verdict":
            d = ev.get("detail") or {}
            last_verdict = d.get("verdict") or d.get("verdict", ev.get("verdict"))
            if isinstance(last_verdict, bool):
                last_verdict = "PASS" if last_verdict else "FAIL"
            break
    if last_verdict and str(last_verdict).upper() == "FAIL":
        failures.append({"ticket": ticket, "ts": last.get("ts"), "event": last.get("event")})
    summaries[ticket] = {
        "last_ts": last.get("ts"),
        "last_event": last.get("event"),
        "last_agent": last.get("agent"),
        "event_count": len(evs),
        "last_verdict": last_verdict,
    }

last_tick = None
for ev in reversed(loop_events):
    if ev.get("event") in ("tick_start", "tick_end"):
        last_tick = ev
        break

result = {
    "files": len(list(runs_dir.glob("*.jsonl"))),
    "ticket_count": len(summaries),
    "loop_events": len(loop_events),
    "last_tick": last_tick,
    "tickets": dict(sorted(summaries.items())),
    "failures": failures,
}

if json_mode:
    print(json.dumps(result, indent=2))
    sys.exit(0)

print(f"Factory ledger — {runs_dir}")
print(f"  files: {result['files']}  tickets traced: {result['ticket_count']}  loop events: {result['loop_events']}")

if last_tick:
    d = last_tick.get("detail") or {}
    run = d.get("run", "—")
    print(f"  last tick: {last_tick.get('event')} @ {last_tick.get('ts')} (run={run})")
else:
    print("  last tick: (none)")

if failures:
    print("  last failures:")
    for f in failures:
        print(f"    - {f['ticket']} @ {f['ts']}")
else:
    print("  last failures: (none)")

openish = [t for t, s in summaries.items() if s.get("last_verdict") not in ("PASS", "Done") and s.get("last_event") != "transition"]
if summaries:
    print("  recent ticket activity:")
    for ticket, s in sorted(summaries.items(), key=lambda x: x[1]["last_ts"] or "", reverse=True)[:8]:
        v = s.get("last_verdict") or "—"
        print(f"    {ticket}: {s['last_event']} ({v}) @ {s['last_ts']}")
PY

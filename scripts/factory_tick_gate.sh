#!/usr/bin/env bash
# Gate: per-ticket machine DoD before qa-loop tick_end.
#
# Reads factory ledger since the latest tick_start. Every scope ticket must have
# a dod_check event with a terminal verdict (DONE, FAIL, RETURN_DEV, SKIP_DEV,
# QA_CONTINUE). PARTIAL, DEFERRED, PASS_PENDING, and BLOCKED are rejected.
# Marathon freeze (impl-qa must be DONE; QA_CONTINUE rejected) applies only when
# marathon_start is logged this tick — otherwise slice-mode QA_CONTINUE is allowed.
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
PROJECT="$ROOT/projects/$SLUG"
[[ -d "$PROJECT" ]] || { echo "GATE CLOSED: no project projects/$SLUG" >&2; exit 1; }

python3 - "$RUNS" "$PROJECT" "$KEYS" <<'PY'
import json, re, sys, pathlib

runs_dir = pathlib.Path(sys.argv[1])
project_dir = pathlib.Path(sys.argv[2])
keys_arg = sys.argv[3].strip() if len(sys.argv) > 3 else ""

JIRA_LINE = re.compile(r"^\s*-\s*\*\*Jira:\*\*\s*(\S+)", re.MULTILINE | re.IGNORECASE)

def ticket_has_tc_file(key):
    tc_dir = project_dir / "test-cases"
    if not tc_dir.is_dir():
        return False
    key_u = key.upper()
    for path in tc_dir.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in JIRA_LINE.finditer(text):
            if m.group(1).upper() == key_u:
                return True
    return False

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
scope_check_found = False
if keys_arg:
    scope_keys = [k.strip() for k in keys_arg.split(",") if k.strip()]
    scope_count = len(scope_keys)
    scope_check_found = True
else:
    for ev in reversed(loop_events):
        if not since_tick(ev):
            break
        if ev.get("event") == "scope_check":
            scope_check_found = True
            d = ev.get("detail") or {}
            scope_keys = d.get("keys") or []
            if isinstance(scope_keys, str):
                scope_keys = [k.strip() for k in scope_keys.split(",") if k.strip()]
            try:
                scope_count = int(d.get("count", len(scope_keys)))
            except (TypeError, ValueError):
                scope_count = len(scope_keys)
            break

if not scope_check_found:
    print(
        "GATE CLOSED: no scope_check since tick_start — run: ./scripts/jira_scope.sh <slug> --log --shell",
        file=sys.stderr,
    )
    sys.exit(1)

TERMINAL = {"DONE", "FAIL", "RETURN_DEV", "SKIP_DEV", "QA_CONTINUE"}
FORBIDDEN = {"PARTIAL", "DEFERRED", "PASS_PENDING", "BLOCKED"}
errors = []

def all_scope_keys_this_tick():
    """Union of keys from every scope_check since tick_start.

    Completed DONE/FAIL/RETURN_DEV tickets drop off the *latest* rescan (count=0 or
    SKIP_DEV-only remainder). Drain detection must still see those earlier keys.
    """
    keys = []
    seen = set()
    for ev in loop_events:
        if not since_tick(ev) or ev.get("event") != "scope_check":
            continue
        d = ev.get("detail") or {}
        raw = d.get("keys") or []
        if isinstance(raw, str):
            raw = [k.strip() for k in raw.split(",") if k.strip()]
        for k in raw:
            k = str(k).strip()
            if k and k not in seen:
                seen.add(k)
                keys.append(k)
    return keys

def has_real_work():
    """True when any ticket from any scope_check this tick resolved to DONE/FAIL/RETURN_DEV."""
    for key in all_scope_keys_this_tick():
        for ev in reversed([ev for ev in load_events(runs_dir / f"{key}.jsonl") if since_tick(ev)]):
            if ev.get("event") == "dod_check":
                if str((ev.get("detail") or {}).get("verdict", "")).upper() in ("DONE", "FAIL", "RETURN_DEV"):
                    return True
                break
    return False

def has_backlog_drained():
    """Explicit last-step marker: agent re-scanned Jira and confirms no unhandled backlog remains."""
    return any(ev.get("event") == "backlog_drained" for ev in loop_events if since_tick(ev))

# Backlog-drain check (skip for --keys targeted testing): whenever real ticket work happened this
# tick (a DONE/FAIL/RETURN_DEV resolution on *any* key seen in any scope_check this tick — not
# only the latest rescan), the agent must log a `backlog_drained` event as the final step —
# proof that jira_scope.sh was re-run after resolving and the queue was checked again
# (never stop at one pass while more work may exist).
if not keys_arg and has_real_work() and not has_backlog_drained():
    errors.append(
        "backlog drain: real ticket work happened this tick but no backlog_drained event logged — "
        "re-run ./scripts/jira_scope.sh <slug> --log --shell as the final step, then log "
        "'./scripts/factory_log.sh <slug> _loop backlog_drained count=<final scope count>' "
        "before tick_end (never stop at one ticket/one scan while more work may exist)"
    )

if scope_count == 0 and not scope_keys:
    if errors:
        print("GATE CLOSED — tick_end not allowed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print("GATE OPEN — scope empty (count=0), exploratory allowed")
    sys.exit(0)

if not scope_keys:
    print("GATE CLOSED: scope_check count>0 but keys missing — re-run jira_scope.sh --log", file=sys.stderr)
    sys.exit(1)

def ticket_has_event(key, event_name):
    return any(ev.get("event") == event_name for ev in load_events(runs_dir / f"{key}.jsonl") if since_tick(ev))

def ticket_dod_verdict(key):
    for ev in reversed([ev for ev in load_events(runs_dir / f"{key}.jsonl") if since_tick(ev)]):
        if ev.get("event") == "dod_check":
            return str((ev.get("detail") or {}).get("verdict", "")).upper()
    return ""

def normalize_status(s):
    return str(s or "").lower().replace("_", " ").strip()

def is_validate_testing(status):
    ns = normalize_status(status)
    return ns == "validate/testing" or (ns.startswith("validate") and "testing" in ns)

def ticket_handoff_status(key):
    """Authoritative Jira status from handoff_read this tick (not dod_check.jira_status)."""
    for ev in reversed([ev for ev in load_events(runs_dir / f"{key}.jsonl") if since_tick(ev)]):
        if ev.get("event") != "handoff_read":
            continue
        d = ev.get("detail") or {}
        if d.get("status"):
            return str(d["status"])
    return ""

def ticket_handoff_labels(key):
    """Labels from handoff_read this tick (factory ownership routing)."""
    for ev in reversed([ev for ev in load_events(runs_dir / f"{key}.jsonl") if since_tick(ev)]):
        if ev.get("event") != "handoff_read":
            continue
        d = ev.get("detail") or {}
        raw = d.get("labels")
        if isinstance(raw, list):
            return [str(x) for x in raw]
        if raw:
            return [x.strip() for x in str(raw).split(",") if x.strip()]
    return []

def is_impl_qa(key):
    return any(str(l).lower() == "impl-qa" for l in ticket_handoff_labels(key))

effective_scope = scope_count if scope_count > 0 else len(scope_keys)

impl_qa_ip = [
    k for k in scope_keys
    if is_impl_qa(k) and normalize_status(ticket_handoff_status(k)) == "in progress"
]

def has_marathon_start():
    """Opt-in marathon: only when marathon_start is logged this tick (_loop or ticket)."""
    for ev in loop_events:
        if since_tick(ev) and ev.get("event") == "marathon_start":
            return True
    for key in impl_qa_ip:
        for ev in load_events(runs_dir / f"{key}.jsonl"):
            if since_tick(ev) and ev.get("event") == "marathon_start":
                return True
    return False

# Slice mode (no marathon_start): QA_CONTINUE may open the gate.
# Marathon mode (marathon_start logged): freeze until impl-qa → DONE.
marathon_frozen = (
    has_marathon_start()
    and bool(impl_qa_ip)
    and not all(ticket_dod_verdict(k) == "DONE" for k in impl_qa_ip)
)
prep_keys = impl_qa_ip if marathon_frozen else scope_keys

if effective_scope > 0:
    has_exploratory = any(ev.get("event") == "exploratory" for ev in loop_events if since_tick(ev))
    if has_exploratory and marathon_frozen:
        errors.append(
            "exploratory forbidden during impl-qa marathon — finish charter to Done first"
        )
    elif has_exploratory:
        for key in scope_keys:
            if ticket_dod_verdict(key) not in TERMINAL:
                errors.append(
                    f"exploratory logged before {key} has terminal dod_check — finish scope retest first"
                )
    for key in prep_keys:
        if not ticket_has_event(key, "handoff_read"):
            errors.append(f"{key}: missing handoff_read — run scripts/jira_handoff.sh <slug> {key} --log")
        if not ticket_has_tc_file(key):
            errors.append(
                f"{key}: missing persisted TC — run scripts/ticket_tc.sh <slug> {key} --title \"…\" [--log]"
            )

def has_transition(events, target="In Progress"):
    for ev in reversed(events):
        if ev.get("event") == "transition":
            d = ev.get("detail") or {}
            to = str(d.get("to", "")).lower()
            if to.replace("_", " ") == target.lower():
                return True
    return False

def ticket_work_started(events, dod):
    """True when QA actually started ticket work this tick (not passive monitor)."""
    if has_transition(events, "In Progress"):
        return True
    for flag in ("retest_attempted", "feature_steps_executed"):
        if str((dod or {}).get(flag, "")).lower() in ("true", "1", "yes"):
            return True
    if any(ev.get("event") in ("factory_autotake", "recording_attached") for ev in events):
        return True
    return False

def require_bug_tracker_evidence(key, dod, errors):
    """When a separate bug/dev ticket was filed, evidence must be on the tracker bug."""
    bug_key = dod.get("bug_filed") or dod.get("dev_ticket")
    if not bug_key:
        return
    if str(dod.get("bug_recording_attached", "")).lower() not in ("true", "1", "yes"):
        errors.append(
            f"{key}: bug {bug_key} requires bug_recording_attached=true "
            f"(record_and_attach.sh on the bug key — Jira or GitHub)"
        )
    if str(dod.get("bug_screenshot_attached", "")).lower() not in ("true", "1", "yes"):
        errors.append(
            f"{key}: bug {bug_key} requires bug_screenshot_attached=true "
            f"(create_bug_issue.py / create_jira_issue.py / github_create_issue.py --attach)"
        )
    if not dod.get("openspec_req") and not dod.get("openspec_scenario"):
        errors.append(
            f"{key}: bug filing requires openspec_req=REQ-… or openspec_scenario=… "
            f"(authority from openspec_read.sh)"
        )

def has_verdict_review_pass(events, dod):
    """Argus lead critique before Done/FAIL/RETURN (skill qa-verdict-review)."""
    if str(dod.get("verdict_review", "")).lower() in ("pass", "true", "1", "yes"):
        return True
    for ev in events:
        if ev.get("event") != "verdict_review":
            continue
        d = ev.get("detail") or {}
        if str(d.get("result", "")).lower() in ("pass", "true", "ok", "1", "yes"):
            return True
    return False

def require_verdict_review(key, events, dod, verdict, errors):
    if verdict not in ("DONE", "FAIL", "RETURN_DEV"):
        return
    if has_verdict_review_pass(events, dod):
        return
    errors.append(
        f"{key}: {verdict} requires verdict_review=pass "
        f"(skill qa-verdict-review → check_verdict_review.sh; "
        f"log verdict_review result=pass or dod_check verdict_review=pass)"
    )

checked = {}

for key in scope_keys:
    if marathon_frozen and key not in impl_qa_ip:
        continue  # dev/feature tickets wait until impl-qa marathon completes
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
        require_bug_tracker_evidence(key, dod, errors)
        require_verdict_review(key, events, dod, verdict, errors)

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
        require_bug_tracker_evidence(key, dod, errors)
        require_verdict_review(key, events, dod, verdict, errors)

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
        if not dod.get("openspec_read"):
            errors.append(f"{key}: DONE requires openspec_read=true (spec authority checked)")
        require_verdict_review(key, events, dod, verdict, errors)
        # Acceptance smoke pack (pantheon#91): when automation/specs/acceptance-smoke.spec.js
        # (or SMOKE_PACK marker) exists, DONE needs smoke_pack=pass on dod or ledger event.
        smoke_spec = project_dir / "automation" / "specs" / "acceptance-smoke.spec.js"
        smoke_marker = project_dir / "automation" / "SMOKE_PACK"
        if smoke_spec.is_file() or smoke_marker.is_file():
            smoke_ok = str(dod.get("smoke_pack", "")).lower() in ("pass", "true", "1", "yes", "ok", "green")
            if not smoke_ok:
                for ev in events:
                    if ev.get("event") != "smoke_pack":
                        continue
                    d = ev.get("detail") or {}
                    if str(d.get("result", "")).lower() in ("pass", "true", "1", "yes", "ok", "green"):
                        smoke_ok = True
                        break
                    if str(d.get("smoke_pack", "")).lower() in ("pass", "true", "1", "yes", "ok", "green"):
                        smoke_ok = True
                        break
            if not smoke_ok:
                # Also accept a loop-level smoke_pack pass this tick
                for ev in loop_events:
                    if not since_tick(ev):
                        continue
                    if ev.get("event") != "smoke_pack":
                        continue
                    d = ev.get("detail") or {}
                    if str(d.get("result", "")).lower() in ("pass", "true", "1", "yes", "ok", "green"):
                        smoke_ok = True
                        break
            if not smoke_ok:
                errors.append(
                    f"{key}: DONE requires smoke_pack=pass when acceptance smoke pack exists "
                    f"(run_automation.sh --suite acceptance-smoke.spec.js; "
                    f"factory_log … smoke_pack result=pass or dod_check smoke_pack=pass)"
                )

    handoff_status = ticket_handoff_status(key)
    if handoff_status:
        js_logged = normalize_status(dod.get("jira_status", ""))
        hs = normalize_status(handoff_status)
        if js_logged and hs != js_logged:
            errors.append(
                f"{key}: dod_check jira_status={dod.get('jira_status')!r} "
                f"mismatches handoff_read status={handoff_status!r} — re-read handoff; never copy stale status"
            )
        if is_validate_testing(handoff_status):
            if verdict == "SKIP_DEV":
                errors.append(
                    f"{key}: SKIP_DEV forbidden when handoff_read is Validate/Testing — "
                    f"full retest required (DONE|FAIL|RETURN_DEV); impl-dev label does not skip V/T"
                )
            elif verdict not in ("DONE", "FAIL", "RETURN_DEV"):
                errors.append(
                    f"{key}: Validate/Testing requires DONE|FAIL|RETURN_DEV (got {verdict})"
                )

    if is_impl_qa(key) and verdict == "SKIP_DEV":
        errors.append(
            f"{key}: SKIP_DEV forbidden on impl-qa — QA-owned charter ticket; "
            f"log QA_CONTINUE with charter_slice + charter_artifact, or Done when acceptance met"
        )

    if marathon_frozen and is_impl_qa(key) and verdict == "QA_CONTINUE":
        errors.append(
            f"{key}: QA_CONTINUE forbidden during impl-qa marathon — work until Done, then tick_end"
        )

    if marathon_frozen and is_impl_qa(key) and verdict != "DONE":
        errors.append(
            f"{key}: impl-qa marathon active — tick_end requires Done (got {verdict})"
        )

    if verdict == "QA_CONTINUE":
        if not is_impl_qa(key):
            errors.append(
                f"{key}: QA_CONTINUE only for impl-qa labeled tickets (handoff_read labels)"
            )
        hs = normalize_status(handoff_status or dod.get("jira_status", ""))
        if hs and hs != "in progress":
            errors.append(
                f"{key}: QA_CONTINUE only when handoff is In Progress (got {handoff_status or dod.get('jira_status')!r})"
            )
        if not dod.get("charter_slice"):
            errors.append(f"{key}: QA_CONTINUE requires charter_slice=<work done this tick>")
        if not dod.get("charter_artifact"):
            errors.append(
                f"{key}: QA_CONTINUE requires charter_artifact=<run folder path updated this tick>"
            )
        if not dod.get("openspec_read"):
            errors.append(f"{key}: QA_CONTINUE requires openspec_read=true")
        if str(dod.get("qa_work_done", "")).lower() not in ("true", "1", "yes"):
            errors.append(f"{key}: QA_CONTINUE requires qa_work_done=true (active charter work, not monitor)")

    if verdict == "SKIP_DEV":
        if not dod.get("note"):
            errors.append(f"{key}: SKIP_DEV requires note")
        if ticket_work_started(events, dod):
            errors.append(
                f"{key}: SKIP_DEV forbidden after work started this tick — "
                f"finish to Done (or FAIL/RETURN_DEV if blocked); do not defer to next tick"
            )
        if handoff_status:
            if normalize_status(handoff_status) != "in progress":
                if not any(
                    "SKIP_DEV forbidden" in e or "handoff_read is Validate/Testing" in e for e in errors
                ):
                    errors.append(
                        f"{key}: SKIP_DEV only when handoff_read status is In Progress (got {handoff_status!r})"
                    )
        else:
            js = normalize_status(dod.get("jira_status", ""))
            if js and js not in ("in progress",):
                errors.append(f"{key}: SKIP_DEV only when jira_status=In Progress (got {dod.get('jira_status')!r})")

    # Same-tick completion: autotake / transition / retest ⇒ must finish, not defer.
    if has_transition(events, "In Progress") and verdict != "DONE":
        if verdict == "SKIP_DEV":
            pass  # already reported above
        elif verdict not in ("FAIL", "RETURN_DEV"):
            errors.append(
                f"{key}: moved to In Progress this tick — must complete to Done before tick_end "
                f"(or FAIL/RETURN_DEV with full blocker path); no partial deferral"
            )

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

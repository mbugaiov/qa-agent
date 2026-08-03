#!/usr/bin/env bash
# Arm the QA loop sleeper — execution-only wakes.
#
# Usage (run this script itself in a background Shell):
#   QA_LOOP_INTERVAL_SEC=1200 bash scripts/arm_qa_loop.sh <slug>
#   bash scripts/arm_qa_loop.sh <slug>   # default interval 1200 (20m)
#
# Kills prior AGENT_LOOP_WAKE_<slug>qa sleepers, prints arm banner, then
# exec's the infinite sleeper (so the background Shell job *is* the arm).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:-}"
[[ -z "$SLUG" ]] && { echo "Usage: arm_qa_loop.sh <slug>" >&2; exit 1; }
if [[ ! "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Invalid slug '$SLUG' — expected ^[a-z0-9][a-z0-9-]*$" >&2
  exit 2
fi

INTERVAL="${QA_LOOP_INTERVAL_SEC:-1200}"
if [[ ! "$INTERVAL" =~ ^[0-9]+$ ]]; then
  echo "Invalid QA_LOOP_INTERVAL_SEC='$INTERVAL' — must be digits only" >&2
  exit 2
fi

SENTINEL="AGENT_LOOP_WAKE_${SLUG}qa"
# NOTE: PROMPT is embedded inside a single-quoted echo string in the sleeper below —
# it must NEVER contain an apostrophe/single-quote character (e.g. write "the task" not
# "the task's"), or the sleeper shell command breaks with a syntax error at wake time.
PROMPT="EXECUTE qa-loop tick NOW for ${SLUG} - full checklist every time, no notify-only mode exists regardless of the wake title or wording: if .cursor/qa-pending-execute.json exists with consumed false, treat as QA_WAKE_EXECUTE and drain that ticket first then ack_qa_pending.ts; tick_start -> qa_scope --log --shell -> per-ticket handoff+OpenSpec+TC+two-pass evidence -> skill qa-verdict-review (write verdict-review artifact, check_verdict_review.sh, factory_log verdict_review result=pass) -> dod_check with verdict_review=pass -> close (jira_close_issue.py/github_close_issue.py or return scripts — blocked without ledger pass) -> evidence (recording/screenshot) -> new/updated regression tests -> drain the backlog (re-run qa_scope.sh again and keep working ticket by ticket, including impl-qa To Do, until a scan returns count=0 or only dev-owned SKIP_DEV remains, then log factory_log.sh backlog_drained) -> factory_tick_gate.sh -> exploratory -> tick_end -> run.md. Do the drain-and-log-backlog_drained step BEFORE factory_tick_gate.sh, not after - do not stop at one ticket per tick. Forbidden: notify-only or status-only replies, no matter how the wake is titled. Forbidden: Done/FAIL/RETURN without qa-verdict-review."

if [[ "$PROMPT" == *"'"* ]]; then
  echo "ERROR: PROMPT contains an apostrophe/single-quote — this breaks the sleeper's echo quoting. Fix arm_qa_loop.sh." >&2
  exit 3
fi

while read -r pid; do
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
done < <(pgrep -f "$SENTINEL" 2>/dev/null || true)
while read -r pid; do
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
done < <(pgrep -f "sleep ${INTERVAL}.*${SENTINEL}" 2>/dev/null || true)

cat <<EOF
QA_LOOP_ARMED slug=${SLUG} interval_sec=${INTERVAL} sentinel=${SENTINEL}
This process is the sleeper (run arm_qa_loop.sh in a background Shell with
notify_on_output pattern: ^${SENTINEL}). On wake: EXECUTE the full checklist
every time (scope+handoffs+DoD+gate+close+evidence+new tests), drain the
backlog ticket by ticket until a scan returns count=0 — no notify-only mode
exists, regardless of how the wake is titled. Skill: qa-loop.
EOF

cd "$ROOT"
export QA_LOOP_INTERVAL_SEC="$INTERVAL"
exec bash -c "while true; do sleep ${INTERVAL}; echo '${SENTINEL} {\"prompt\":\"${PROMPT}\"}'; done"

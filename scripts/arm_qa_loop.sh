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
PROMPT="EXECUTE qa-loop tick NOW for ${SLUG}: tick_start → jira_scope --log --shell → per-ticket handoff/DoD → factory_tick_gate → exploratory → tick_end → run.md. Forbidden: notify-only or status-only replies."

while read -r pid; do
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
done < <(pgrep -f "$SENTINEL" 2>/dev/null || true)
while read -r pid; do
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
done < <(pgrep -f "sleep ${INTERVAL}.*${SENTINEL}" 2>/dev/null || true)

cat <<EOF
QA_LOOP_ARMED slug=${SLUG} interval_sec=${INTERVAL} sentinel=${SENTINEL}
This process is the sleeper (run arm_qa_loop.sh in a background Shell with
notify_on_output pattern: ^${SENTINEL}). On wake: EXECUTE full tick — never
notify-only. Skill: qa-loop.
EOF

cd "$ROOT"
export QA_LOOP_INTERVAL_SEC="$INTERVAL"
exec bash -c "while true; do sleep ${INTERVAL}; echo '${SENTINEL} {\"prompt\":\"${PROMPT}\"}'; done"

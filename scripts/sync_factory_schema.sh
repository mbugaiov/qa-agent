#!/usr/bin/env bash
# Sync factory/schema.md from projects/_template into a live project.
#
# Usage:
#   scripts/sync_factory_schema.sh <slug>           # full copy (default)
#   scripts/sync_factory_schema.sh <slug> --overlay # keep project examples; refresh pointer + required fields
#
# Engines ship the canonical schema in _template; live projects must not drift.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:-}"
MODE="${2:-}"
[[ -n "$SLUG" ]] || { echo "Usage: sync_factory_schema.sh <slug> [--overlay]" >&2; exit 1; }
SRC="$ROOT/projects/_template/factory/schema.md"
DEST_DIR="$ROOT/projects/$SLUG/factory"
DEST="$DEST_DIR/schema.md"
[[ -f "$SRC" ]] || { echo "Missing template schema: $SRC" >&2; exit 1; }
[[ -d "$ROOT/projects/$SLUG" ]] || { echo "No project: projects/$SLUG" >&2; exit 1; }
mkdir -p "$DEST_DIR"

if [[ "$MODE" == "--overlay" ]]; then
  cat >"$DEST" <<EOF
# Factory run ledger — ${SLUG} project examples

Per-ticket trace files: \`projects/${SLUG}/factory/runs/<KEY>.jsonl\`
Loop-level events: \`projects/${SLUG}/factory/runs/_loop.jsonl\`

**Canonical schema (engine):** \`projects/_template/factory/schema.md\` — DoD gate,
\`dod_check\`, \`verdict_review\`, \`factory_tick_gate.sh\`.

**Close/return hard gate:** \`jira_close_issue.py\` / \`github_close_issue.py\` /
\`jira_return_in_progress.py\` / \`github_return_to_dev.py\` refuse live transitions
unless the ticket ledger has \`verdict_review=pass\` (skill \`qa-verdict-review\` →
\`check_verdict_review.sh\`). Escape hatch: \`--allow-missing-verdict-review\` only.

## ${SLUG}-specific examples

### Ticket closed Done

\`\`\`bash
# After two-pass evidence — skill qa-verdict-review (not a third browser pass):
cat > projects/${SLUG}/runs/<run>/verdict-review-<KEY>.md <<'VR'
## Summary
<KEY> — PASS candidate — evidence matches OpenSpec THEN.

## Blocking gaps
None.

## Suggestions
- None.
VR
bash scripts/check_verdict_review.sh projects/${SLUG}/runs/<run>/verdict-review-<KEY>.md
./scripts/factory_log.sh ${SLUG} <KEY> verdict_review result=pass artifact=runs/<run>/verdict-review-<KEY>.md
./scripts/factory_log.sh ${SLUG} <KEY> dod_check \\
  verdict=DONE two_pass=true canonical_source=true \\
  buildid_gate=MATCH recording_attached=true \\
  retest_attempted=true feature_steps_executed=true openspec_read=true \\
  verdict_review=pass
python3 scripts/jira_close_issue.py --project projects/${SLUG} --key <KEY> \\
  --to Done --comment "QA PASS — see ledger + recording"
./scripts/factory_log.sh ${SLUG} <KEY> transition to=Done
\`\`\`

### Return V/T to dev

\`\`\`bash
bash scripts/check_verdict_review.sh projects/${SLUG}/runs/<run>/verdict-review-<KEY>.md
./scripts/factory_log.sh ${SLUG} <KEY> verdict_review result=pass artifact=runs/<run>/verdict-review-<KEY>.md
./scripts/factory_log.sh ${SLUG} <KEY> dod_check \\
  verdict=RETURN_DEV dev_ticket=<BUG> transition=In\\ Progress \\
  retest_attempted=true alternate_locators_tried=true feature_steps_executed=true \\
  openspec_read=true openspec_req=REQ-… verdict_review=pass \\
  bug_filed=<BUG> bug_recording_attached=true bug_screenshot_attached=true
python3 scripts/jira_return_in_progress.py --project projects/${SLUG} --key <KEY> \\
  --reason "…" --dev-ticket <BUG> --steps-tried "…"
\`\`\`

Sync this overlay: \`./scripts/sync_factory_schema.sh ${SLUG} --overlay\`
EOF
  echo "wrote overlay schema -> $DEST"
  exit 0
fi

cp "$SRC" "$DEST"
echo "synced full schema -> $DEST"

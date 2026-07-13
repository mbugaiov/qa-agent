#!/usr/bin/env bash
# Run headless Cursor code review on branch diff; write review.md and enforce gate.
#
# Usage:
#   scripts/run_code_review.sh [base-branch]
#   BASE=main scripts/run_code_review.sh
#
# Requires: cursor-agent on PATH, CURSOR_API_KEY in env (or projects/<slug>/.secrets/cursor.env).
# Local dry-run without agent: write a draft review.md and run check_review_gate.sh manually.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BASE="${1:-${BASE:-main}}"

if ! command -v cursor-agent >/dev/null 2>&1; then
  echo "ERROR: cursor-agent not on PATH — install Cursor CLI (see HOST_SETUP.md)" >&2
  exit 1
fi

if [[ -z "${CURSOR_API_KEY:-}" ]]; then
  echo "ERROR: CURSOR_API_KEY not set" >&2
  exit 1
fi

git fetch origin "$BASE" --quiet 2>/dev/null || true

PROMPT="You are the automated reviewer for this GitHub pull request. Follow the review guide at .cursor/rules/code-review.mdc (and AGENTS.md + other .cursor/rules it references). Review ONLY this branch's changes vs origin/${BASE} — begin with: git --no-pager diff origin/${BASE}...HEAD — and produce exactly the output sections that guide specifies."

echo "Running cursor-agent review (base=origin/${BASE})..."
if cursor-agent --force --api-key "$CURSOR_API_KEY" --output-format text -p "$PROMPT" > review.md; then
  :
else
  echo "cursor-agent exited non-zero — see review.md if partial"
fi

if [[ ! -s review.md ]]; then
  echo "Cursor review produced no output (see build log above)." > review.md
fi

cat review.md
echo ""
bash scripts/check_review_gate.sh review.md

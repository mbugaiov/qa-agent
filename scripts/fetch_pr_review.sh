#!/usr/bin/env bash
# Extract latest Cursor CR comment body from a GitHub PR into review.md
#
# Usage: scripts/fetch_pr_review.sh [pr-number]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PR="${1:-}"
OUT="${REVIEW_OUT:-review.md}"

if [[ -z "$PR" ]]; then
  PR=$(gh pr view --json number -q .number 2>/dev/null) || {
    echo "Usage: fetch_pr_review.sh <pr-number>" >&2
    exit 1
  }
fi

BODY=$(gh pr view "$PR" --comments --json comments -q \
  '[.comments[] | select(.body | contains("qa-agent-cursor-review"))] | last | .body // empty')

if [[ -z "$BODY" ]]; then
  echo "No CR comment found on PR #$PR" >&2
  exit 1
fi

printf '%s' "$BODY" | python3 - "$OUT" <<'PY'
import sys
from pathlib import Path
body = sys.stdin.read()
if not body.strip():
    print("No CR comment found", file=sys.stderr)
    sys.exit(1)
marker = "<!-- qa-agent-cursor-review -->"
if marker in body:
    body = body.split(marker, 1)[1]
if "## Cursor automated review" in body:
    body = body.split("## Cursor automated review", 1)[1]
path = sys.argv[1]
Path(path).write_text(body.strip() + "\n", encoding="utf-8")
print(f"Wrote {path} from PR comment")
PY

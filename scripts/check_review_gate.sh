#!/usr/bin/env bash
# Fail when Cursor review output has blocking issues (RQ-1647 pattern).
#
# Usage: scripts/check_review_gate.sh [review.md]
# Exit 0 = pass (LGTM or Blocking issues: None). Exit 1 = blockers or malformed output.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="${1:-review.md}"
python3 "$ROOT/scripts/review_gate.py" "$FILE"

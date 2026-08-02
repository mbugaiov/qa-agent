#!/usr/bin/env bash
# Fail when Argus verdict-review has blocking gaps.
# Usage: scripts/check_verdict_review.sh <verdict-review.md>
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="${1:-}"
[[ -n "$FILE" ]] || { echo "Usage: check_verdict_review.sh <verdict-review.md>" >&2; exit 1; }
[[ -f "$FILE" ]] || { echo "Missing: $FILE" >&2; exit 1; }
exec python3 "$ROOT/scripts/verdict_review_gate.py" "$FILE"

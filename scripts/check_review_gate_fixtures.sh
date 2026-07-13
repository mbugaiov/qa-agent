#!/usr/bin/env bash
# Validate check_review_gate.sh against historical review.md fixtures.
#
# Usage: scripts/check_review_gate_fixtures.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES="$ROOT/tests/fixtures/review-gate"
GATE="$ROOT/scripts/check_review_gate.sh"

# file:expect pairs (bash 3.x compatible — no associative arrays)
FIXTURES_LIST="
lgtm.md:pass
blocking-none.md:pass
blocking-items.md:fail
no-output.md:fail
unstructured-error.md:fail
empty-blocking-section.md:fail
missing-blocking-header.md:fail
false-lgtm-after-blockers.md:fail
"

FAIL=0
COUNT=0
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  file="${line%%:*}"
  want="${line#*:}"
  path="$FIXTURES/$file"
  COUNT=$((COUNT + 1))
  [[ -f "$path" ]] || { echo "missing fixture: $path"; FAIL=1; continue; }
  if "$GATE" "$path" >/dev/null 2>&1; then
    got=pass
  else
    got=fail
  fi
  if [[ "$got" != "$want" ]]; then
    echo "check_review_gate_fixtures: FAIL $file expected $want, gate $got"
    FAIL=1
  fi
done <<< "$FIXTURES_LIST"

if [[ "$FAIL" -ne 0 ]]; then
  exit 1
fi
echo "check_review_gate_fixtures: OK ($COUNT fixtures)"

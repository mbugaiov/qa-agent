#!/usr/bin/env bash
# Portability gate: tracked engine files must not hardcode a live project slug or product.
#
# Usage: scripts/portability_check.sh
# Exit 0 = clean. Exit 1 = forbidden pattern in tracked files.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Patterns that belong in qa-agent-projects-* repos, not the engine.
FORBIDDEN='(\blrm\b|sol-ark|solark|qa_lab_resource_management|/Users/max/Downloads)'

PATHS=(
  .cursor
  scripts
  templates
  tests
  AGENTS.md
  PORTABILITY.md
  SETUP.md
  HOST_SETUP.md
  README.md
)

FAIL=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  [[ "$f" == "scripts/portability_check.sh" ]] && continue
  while IFS= read -r line; do
    # Allow illustrative slug examples in prose.
    echo "$line" | grep -q 'e\.g\. `<slug>`' && continue
    echo "$line" | grep -q 'e\.g\. <slug>' && continue
    echo "portability leak: $line"
    FAIL=1
  done < <(git grep -nE "$FORBIDDEN" -- "$f" 2>/dev/null || true)
done < <(git ls-files "${PATHS[@]}")

if [[ "$FAIL" -eq 0 ]]; then
  echo "portability: OK (no project-specific leaks in tracked engine files)"
fi
exit "$FAIL"

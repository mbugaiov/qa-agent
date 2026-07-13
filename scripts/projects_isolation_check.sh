#!/usr/bin/env bash
# Projects isolation gate: the engine repo must never track live project data.
#
# Only projects/_template/ belongs in git. Per-app folders (projects/<slug>/) live in
# separate repos, submodules, or local clones — see PORTABILITY.md.
#
# Usage: scripts/projects_isolation_check.sh
# Exit 0 = clean. Exit 1 = live project file(s) tracked or gitignore gap.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0

# 1. Tracked files under projects/ must all live in _template/
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  case "$f" in
    projects/_template/*) ;;
    *)
      echo "project leak (tracked in git): $f"
      FAIL=1
      ;;
  esac
done < <(git ls-files 'projects/' 2>/dev/null || true)

# 2. .gitignore must block generic live slugs (not just one product)
if ! grep -qE '^projects/\*' .gitignore; then
  echo "gitignore gap: missing 'projects/*' rule"
  FAIL=1
fi
if ! grep -q '!projects/_template/' .gitignore; then
  echo "gitignore gap: missing '!projects/_template/' exception"
  FAIL=1
fi

# 3. Representative live-project paths must be ignored (even if absent on disk)
LIVE_PROBES=(
  projects/acme-corp/project.yaml
  projects/acme-corp/project-memory.md
  projects/acme-corp/runs/2026-07-01-smoke-x/run.md
  projects/acme-corp/.secrets/jira.env
  projects/acme-corp/factory/runs/TST-1.jsonl
  projects/qa-selftest/project.yaml
)
for probe in "${LIVE_PROBES[@]}"; do
  if git check-ignore -q "$probe" 2>/dev/null; then
    :
  else
    echo "gitignore gap: $probe is not ignored — live project data could be committed"
    FAIL=1
  fi
done

# 4. Symlinks to external project trees must not be tracked
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  [[ -L "$f" ]] || continue
  case "$f" in
    projects/_template/*) ;;
    *)
      echo "project leak (tracked symlink): $f -> $(readlink "$f" 2>/dev/null || echo '?')"
      FAIL=1
      ;;
  esac
done < <(git ls-files 'projects/' 2>/dev/null || true)

if [[ "$FAIL" -eq 0 ]]; then
  TRACKED=$(git ls-files 'projects/' 2>/dev/null | wc -l | tr -d ' ')
  echo "projects isolation: OK (only projects/_template/ tracked; ${TRACKED} template file(s); live slugs gitignored)"
fi
exit "$FAIL"

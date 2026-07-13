#!/usr/bin/env bash
# Auto-fix blocking code-review findings; re-run gates and optional re-review.
#
# Usage:
#   bash scripts/cr_autofix.sh [--review review.md] [--base main]
#   bash scripts/cr_autofix.sh --pr 42 [--base main]
#   bash scripts/cr_autofix.sh --ci [--base main]   # commit+push when fixes applied (CI)
#
# Env: CURSOR_API_KEY, CR_AUTOFIX_MAX (default 3)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REVIEW="review.md"
BASE="${BASE:-main}"
PR=""
CI=0
MAX="${CR_AUTOFIX_MAX:-3}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --review) REVIEW="${2:-}"; shift 2 ;;
    --base) BASE="${2:-}"; shift 2 ;;
    --pr) PR="${2:-}"; shift 2 ;;
    --ci) CI=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -n "$PR" ]]; then
  REVIEW_OUT="$REVIEW" bash scripts/fetch_pr_review.sh "$PR" || exit 1
fi

if [[ ! -f "$REVIEW" ]]; then
  echo "ERROR: no review file at $REVIEW (run run_code_review.sh or fetch_pr_review.sh first)" >&2
  exit 1
fi

if bash scripts/check_review_gate.sh "$REVIEW" >/dev/null 2>&1; then
  echo "cr_autofix: review gate already open — nothing to fix"
  exit 0
fi

# PR-level cap in CI: count prior autofix commits on this branch
if [[ "$CI" -eq 1 ]]; then
  git fetch origin "$BASE" --quiet 2>/dev/null || true
  AUTOFIX_COUNT=$(git log "origin/${BASE}..HEAD" --oneline 2>/dev/null | grep -c '\[cr-autofix\]' || true)
  PR_CAP="${CR_AUTOFIX_PR_MAX:-2}"
  if [[ "$AUTOFIX_COUNT" -ge "$PR_CAP" ]]; then
    echo "cr_autofix: PR-level cap reached ($AUTOFIX_COUNT >= $PR_CAP) — escalate to human" >&2
    exit 1
  fi
fi

if [[ -z "${CURSOR_API_KEY:-}" ]]; then
  echo "ERROR: CURSOR_API_KEY required for auto-fix" >&2
  exit 1
fi

if ! command -v cursor-agent >/dev/null 2>&1; then
  echo "ERROR: cursor-agent not on PATH" >&2
  exit 1
fi

attempt=1
while [[ "$attempt" -le "$MAX" ]]; do
  echo "== cr_autofix attempt $attempt/$MAX =="
  BLOCKERS=$(python3 - "$REVIEW" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("review_gate", "scripts/review_gate.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
text = Path(sys.argv[1]).read_text(encoding="utf-8")
sec = mod.extract_blocking_section(text) or text[:4000]
print(sec)
PY
)

  PROMPT="You are fixing blocking code-review findings on the qa-agent ENGINE repo.

Read .cursor/rules/cr-autofix.mdc and .cursor/rules/code-review.mdc.

BLOCKING ISSUES TO FIX (from review):
${BLOCKERS}

Instructions:
1. Fix every blocking issue in the working tree (root cause — do not weaken gates or fake review output).
2. Run: bash scripts/pre_merge_check.sh — must pass before you finish.
3. Do NOT commit unless --ci mode (human/local: leave changes unstaged for the user).

Current branch diff vs origin/${BASE}:
git --no-pager diff origin/${BASE}...HEAD 2>/dev/null || git --no-pager diff HEAD~5...HEAD"

  echo "Running cursor-agent fix..."
  cursor-agent --force --api-key "$CURSOR_API_KEY" --output-format text -p "$PROMPT" || true

  echo "== pre_merge_check =="
  if ! bash scripts/pre_merge_check.sh; then
    echo "pre_merge_check failed on attempt $attempt"
    attempt=$((attempt + 1))
    continue
  fi

  # CI: commit fixes before re-review so origin/${BASE}...HEAD includes them; push only if gate opens.
  if [[ "$CI" -eq 1 ]]; then
    git config user.name "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    if ! git diff --quiet || ! git diff --cached --quiet; then
      git add -A
      git commit -m "fix(cr): address blocking review findings [cr-autofix]"
      echo "cr_autofix: committed fixes locally (pre re-review)"
    fi
  fi

  echo "== re-review =="
  git fetch origin "$BASE" --quiet 2>/dev/null || true
  if [[ "$CI" -eq 1 ]]; then
    RPROMPT="Follow .cursor/rules/code-review.mdc. Review ONLY git diff origin/${BASE}...HEAD (includes the fix commit) — produce exactly the required output sections."
  else
    RPROMPT="Follow .cursor/rules/code-review.mdc. Review ALL pending changes: git diff origin/${BASE}...HEAD plus git diff and git diff --cached for unstaged/staged fixes — produce exactly the required output sections."
  fi
  cursor-agent --force --api-key "$CURSOR_API_KEY" --output-format text -p "$RPROMPT" > "$REVIEW" || true
  [[ -s "$REVIEW" ]] || echo "Cursor review produced no output (see build log above)." > "$REVIEW"

  if bash scripts/check_review_gate.sh "$REVIEW"; then
    echo "cr_autofix: gate open after attempt $attempt"
    if [[ "$CI" -eq 1 ]]; then
      if ! git push; then
        echo "cr_autofix: git push failed" >&2
        exit 1
      fi
      echo "cr_autofix: pushed fix commit"
    fi
    exit 0
  fi

  echo "Review gate still closed after attempt $attempt"
  cat "$REVIEW"
  attempt=$((attempt + 1))
done

echo "cr_autofix: exhausted $MAX attempts — manual intervention required" >&2
exit 1

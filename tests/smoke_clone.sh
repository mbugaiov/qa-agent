#!/usr/bin/env bash
# Validate that SETUP.md / README quickstart works from a fresh clone.
#
# Usage:
#   bash tests/smoke_clone.sh              # clone github.com/mbugaiov/qa-agent to a temp dir
#   bash tests/smoke_clone.sh --local      # use current repo (skip clone)
#   bash tests/smoke_clone.sh --keep       # do not delete temp clone on success
#
# Exit 0 = engine + onboarding commands work offline (no Jira network, no app server).
set -uo pipefail

LOCAL=0
KEEP=0
REPO_URL="${QA_AGENT_REPO_URL:-https://github.com/mbugaiov/qa-agent.git}"
SLUG="smoke-app"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local) LOCAL=1; shift ;;
    --keep) KEEP=1; shift ;;
    *) echo "Usage: smoke_clone.sh [--local] [--keep]" >&2; exit 1 ;;
  esac
done

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ✓ $1"; }
no()  { FAIL=$((FAIL+1)); echo "  ✗ $1"; }

WORKDIR=""
cleanup() {
  [[ "$KEEP" -eq 1 || -z "$WORKDIR" || "$LOCAL" -eq 1 ]] && return 0
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

if [[ "$LOCAL" -eq 1 ]]; then
  WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  ok "using local repo: $WORKDIR"
else
  WORKDIR="$(mktemp -d /tmp/qa-agent-smoke-XXXXXX)"
  git clone --depth 1 "$REPO_URL" "$WORKDIR" >/dev/null 2>&1 \
    && ok "cloned $REPO_URL" || { no "git clone failed"; exit 1; }
fi

cd "$WORKDIR"

echo "== Engine self-tests =="
bash tests/run_tests.sh >/dev/null 2>&1 && ok "tests/run_tests.sh (68 checks)" || no "tests/run_tests.sh"

echo "== SETUP §3: new_project =="
./scripts/new_project.sh "$SLUG" https://staging.example.com "Smoke App" >/dev/null 2>&1 \
  && ok "new_project.sh $SLUG" || no "new_project.sh"
[[ -f "projects/$SLUG/project.yaml" ]] && ok "project.yaml created" || no "project.yaml"
grep -q 'Smoke App' "projects/$SLUG/project-memory.md" 2>/dev/null \
  && ok "placeholders filled in project-memory.md" || no "project-memory placeholders"

echo "== SETUP §10: new_run =="
./scripts/new_run.sh "$SLUG" smoke "clone smoke test" >/dev/null 2>&1 \
  && ok "new_run.sh smoke" || no "new_run.sh"
RUN=$(ls -d projects/$SLUG/runs/*smoke* 2>/dev/null | head -1)
[[ -n "$RUN" && -f "$RUN/run.md" ]] && ok "run folder + run.md" || no "run artifacts"

echo "== SETUP §6e: Jira gate (no secrets) =="
OUT=$(./scripts/jira_status.sh "$SLUG" 2>&1)
echo "$OUT" | grep -qi inactive && ok "jira_status inactive without jira.env" || no "jira_status should be inactive ($OUT)"

echo "== SETUP §7: server (no secrets yet) =="
if [[ ! -f "projects/$SLUG/.secrets/server.env" ]]; then
  ok "server.env absent (expected before SETUP §7)"
else
  ./scripts/server_ctl.sh "$SLUG" status 2>&1 | grep -qi down && ok "server status DOWN" || no "server status"
fi

echo "== Docs present =="
for f in SETUP.md HOST_SETUP.md PORTABILITY.md AGENTS.md README.md; do
  [[ -f "$f" ]] && ok "$f" || no "missing $f"
done

echo "== Template automation README =="
grep -q 'scripts/run_automation.sh' projects/_template/automation/README.md 2>/dev/null \
  && ok "automation README uses engine-root script paths" || no "automation README paths"

echo ""
echo "RESULT: $PASS passed, $FAIL failed"
[[ "$KEEP" -eq 1 && "$LOCAL" -eq 0 ]] && echo "Clone kept at: $WORKDIR"
echo ""
echo "Not covered by this smoke test (manual per SETUP.md / HOST_SETUP.md):"
echo "  - gh auth login + gh auth setup-git (./scripts/gh_auth_check.sh)"
echo "  - ~/.cursor/skills/ (qa-site-analysis, qa-test-execution, qa-report-generation)"
echo "  - Browser MCP + live app under test"
echo "  - .secrets/jira.env, server.env, credentials.json"
[[ "$FAIL" -eq 0 ]]

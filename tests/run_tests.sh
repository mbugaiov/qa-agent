#!/usr/bin/env bash
# Self-tests for the QA Agent engine: verify scripts, rules, skills, and templates
# behave correctly. OFFLINE & side-effect-free — uses a throwaway project, --dry-run for
# Jira (no network, no ticket creation), and cleans up after itself.
#
# Run:  bash tests/run_tests.sh        (exit 0 = all pass)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
SLUG="qa-selftest"
PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ✓ $1"; }
no()  { FAIL=$((FAIL+1)); echo "  ✗ $1"; }
have(){ [[ -e "$1" ]] && ok "exists: $1" || no "missing: $1"; }
grep_ok(){ grep -q "$1" "$2" 2>/dev/null && ok "$3" || no "$3"; }

cleanup(){ rm -rf "projects/$SLUG"; }
trap cleanup EXIT
cleanup

echo "== 1. new_project.sh scaffolds a project =="
./scripts/new_project.sh "$SLUG" https://test.local "Self Test" >/dev/null 2>&1 || no "new_project.sh ran"
for p in project.yaml project-memory.md requirements specs test-cases runs reports automation/specs .secrets jira.env.example server.env.example; do
  have "projects/$SLUG/$p"
done

echo "== 2. new_run.sh seeds artifacts per type =="
./scripts/new_run.sh "$SLUG" exploratory "probe x" >/dev/null 2>&1
EX=$(ls -d projects/$SLUG/runs/*exploratory* 2>/dev/null | head -1)
[[ -f "$EX/exploratory-session.md" && -f "$EX/run.md" ]] && ok "exploratory: run.md + exploratory-session.md" || no "exploratory artifacts"
[[ ! -f "$EX/execution-log.md" ]] && ok "exploratory: no execution-log (correct)" || no "exploratory should not seed execution-log"
./scripts/new_run.sh "$SLUG" full "acc y" >/dev/null 2>&1
FU=$(ls -d projects/$SLUG/runs/*full* 2>/dev/null | head -1)
for f in run.md execution-log.md traceability-matrix.md manual-test-plan.md risk-register.md acceptance-report.md; do
  [[ -f "$FU/$f" ]] && ok "full: $f" || no "full missing $f"
done

echo "== 3. Jira gate: inactive without creds =="
OUT=$(./scripts/jira_status.sh "$SLUG" 2>&1); echo "$OUT" | grep -q inactive && ok "jira_status inactive (no creds)" || no "jira_status should be inactive"
# create_jira_issue is a no-op (not error) when unconfigured
OUT=$(python3 scripts/create_jira_issue.py --project projects/$SLUG --summary x --description y --severity S3 2>&1)
echo "$OUT" | grep -qi "skipping" && ok "create_jira_issue no-op when unconfigured" || no "create should no-op (got: $OUT)"

echo "== 4. Jira active + dry-run payload =="
cat > "projects/$SLUG/.secrets/jira.env" <<EOF
JIRA_BASE_URL=https://test-co.atlassian.net
JIRA_EMAIL=qa@test-co.io
JIRA_API_TOKEN=tok_realish_123
JIRA_PROJECT_KEY=TST
JIRA_ISSUE_TYPE=Bug
JIRA_EPIC_FOR_TASKS_BUGS=https://test-co.atlassian.net/browse/TST-1
JIRA_ASSIGNEE_ACCOUNT_ID=acc:123
JIRA_BOARD_ID=99
JIRA_SPRINT_FIELD=customfield_10020
JIRA_STORYPOINTS_FIELD=customfield_10033
EOF
./scripts/jira_status.sh "$SLUG" 2>&1 | grep -q active && ok "jira_status active with real creds" || no "jira_status should be active"
DRY=$(python3 scripts/create_jira_issue.py --project projects/$SLUG --summary "t" --description "d" --severity S2 --dry-run 2>/dev/null)
echo "$DRY" | grep -q '"key": "TST"' && ok "payload project=TST" || no "payload project key"
echo "$DRY" | grep -q '"key": "TST-1"' && ok "payload parent epic=TST-1" || no "payload epic parent"
echo "$DRY" | grep -q '"accountId": "acc:123"' && ok "payload assignee set" || no "payload assignee"
echo "$DRY" | grep -q 'Story points: 3' && ok "story points by severity (S2=3)" || no "story points default"
echo "$DRY" | grep -q 'add-to-active-sprint: True' && ok "sprint plan present" || no "sprint plan"
DRY4=$(python3 scripts/create_jira_issue.py --project projects/$SLUG --summary "t" --description "d" --severity S2 --labels confirmed-defect --dry-run 2>/dev/null)
echo "$DRY4" | grep -q '"impl-dev"' && ok "confirmed-defect adds impl-dev" || no "confirmed-defect should add impl-dev"

echo "== 4b. Jira ADF: Markdown headings + Gherkin code blocks =="
python3 scripts/test_jira_adf.py -q 2>/dev/null && ok "jira_adf unit tests" || no "jira_adf unit tests"
MD='## Business context

```gherkin
Given x
When y
Then z
```

- item one
'
DRY3=$(python3 scripts/create_jira_issue.py --project projects/$SLUG --summary t --description "$MD" --severity S2 --dry-run 2>/dev/null)
echo "$DRY3" | grep -q '"type": "heading"' && ok "ADF has heading" || no "ADF heading"
echo "$DRY3" | grep -q '"type": "codeBlock"' && ok "ADF has codeBlock" || no "ADF codeBlock"
echo "$DRY3" | grep -q '"type": "bulletList"' && ok "ADF has bulletList" || no "ADF bulletList"

echo "== 5. Per-project isolation: ambient env must NOT override file =="
DRY2=$(JIRA_BASE_URL="https://EVIL.atlassian.net" JIRA_PROJECT_KEY="EVIL" python3 scripts/create_jira_issue.py --project projects/$SLUG --summary t --description d --severity S4 --dry-run 2>/dev/null)
echo "$DRY2" | grep -q 'test-co.atlassian.net' && ! echo "$DRY2" | grep -q 'EVIL' && ok "ambient env ignored (file wins)" || no "ISOLATION LEAK: ambient env affected payload"

echo "== 6. check_coverage.py REQ→SC→TC =="
printf '| REQ-001 | x |\n| REQ-002 | y |\n' > "projects/$SLUG/requirements/requirements.md"
printf '## SC-001\n- Covers: REQ-001\n' > "projects/$SLUG/specs/auth.md"
printf '| TC-A-001 | t | SC-001 | REQ-001 |\n' > "projects/$SLUG/test-cases/test-cases.md"
python3 scripts/check_coverage.py "projects/$SLUG" >/dev/null 2>&1 && no "coverage should FAIL (REQ-002 has no SC)" || ok "coverage detects gap (exit!=0)"
printf '\n## SC-002\n- Covers: REQ-002\n' >> "projects/$SLUG/specs/auth.md"
printf '| TC-A-002 | t | SC-002 | REQ-002 |\n' >> "projects/$SLUG/test-cases/test-cases.md"
python3 scripts/check_coverage.py "projects/$SLUG" >/dev/null 2>&1 && ok "coverage passes when complete" || no "coverage should pass"

echo "== 7. generate_docx_report.py =="
mkdir -p "projects/$SLUG/runs/2026-01-01-smoke-x"
printf '# QA Report\n\n## Metrics\n\n| A | B |\n|---|---|\n| 1 | 2 |\n' > "projects/$SLUG/runs/2026-01-01-smoke-x/report.md"
python3 scripts/generate_docx_report.py "projects/$SLUG/runs/2026-01-01-smoke-x/report.md" >/dev/null 2>&1
ls "projects/$SLUG/reports/"*.docx >/dev/null 2>&1 && ok "DOCX generated" || no "DOCX not generated"

echo "== 8. server_ctl.sh safety =="
cat > "projects/$SLUG/.secrets/server.env" <<EOF
SERVER_URL=http://localhost:59999
SERVER_CWD=/tmp
SERVER_START="true"
SERVER_READY_TIMEOUT=3
EOF
./scripts/server_ctl.sh "$SLUG" status 2>&1 | grep -qi down && ok "server status DOWN (nothing running)" || no "server status"
./scripts/server_ctl.sh "$SLUG" down 2>&1 | grep -qi "not started by us" && ok "server down no-ops without pidfile" || no "server down safety"
./scripts/server_ctl.sh "$SLUG" sync 2>&1 | grep -qi "nothing to sync" && ok "sync no-ops when SERVER_GIT_SYNC unset" || no "sync gating"

echo "== 9. Skills + rule frontmatter =="
for s in qa-runs qa-phases qa-loop qa-server qa-jira qa-security qa-openspec qa-test-data qa-code-review token-efficient-ops usage-accounting; do
  f=".cursor/skills/$s/SKILL.md"
  { grep -q "^name:" "$f" && grep -q "^description:" "$f"; } && ok "skill $s has name+description" || no "skill $s frontmatter"
done
for r in qa-engine token-efficiency usage-accounting qa-team; do
  grep -q "^description:" ".cursor/rules/$r.mdc" && ok "rule $r has frontmatter" || no "rule $r frontmatter"
done

echo "== 9b. Portability doc + no engine LRM script =="
have PORTABILITY.md
[[ ! -f scripts/create_l5_jira_tickets.sh ]] && ok "LRM factory script not in engine scripts/" || no "engine should not ship create_l5_jira_tickets.sh"
grep_ok "projects/<slug>" PORTABILITY.md "PORTABILITY.md is slug-generic"
chmod +x scripts/portability_check.sh 2>/dev/null || true
./scripts/portability_check.sh && ok "portability_check clean" || no "portability_check leaks"
have .github/workflows/ci.yml

echo "== 9c. Projects isolation (no live project data in git) =="
have scripts/projects_isolation_check.sh
chmod +x scripts/projects_isolation_check.sh 2>/dev/null || true
./scripts/projects_isolation_check.sh && ok "projects_isolation_check clean" || no "projects_isolation_check failed"
# Negative probe: a fake live slug path must stay untrackable
FAKE_LIVE="projects/isolation-probe-live/project.yaml"
mkdir -p "projects/isolation-probe-live"
printf 'name: probe\n' > "$FAKE_LIVE"
git check-ignore -q "$FAKE_LIVE" && ok "live project paths are gitignored" || no "live project path not gitignored"
git ls-files --error-unmatch "$FAKE_LIVE" >/dev/null 2>&1 && no "live project file must not be tracked" || ok "live project file not tracked"
rm -rf "projects/isolation-probe-live"

echo "== 10. AGENTS.md index points to real skills =="
for s in qa-runs qa-phases qa-loop qa-server qa-jira qa-security qa-openspec qa-test-data qa-code-review token-efficient-ops usage-accounting; do
  grep_ok "\`$s\`" AGENTS.md "AGENTS.md references skill $s"
done

echo "== 11. L5 unattended =="
rm -f "projects/$SLUG/.secrets/jira.env"
./scripts/reopen_regression.py --project "projects/$SLUG" --key TST-0 --reason "selftest" 2>&1 | grep -qi "skipping reopen" && ok "reopen_regression no-op when Jira unconfigured" || no "reopen_regression gating"
# reopen_regression --dry-run prints intended transition (configured creds not required for dry-run path? it gates first) -> just check help/args parse
./scripts/reopen_regression.py --help >/dev/null 2>&1 && ok "reopen_regression args parse" || no "reopen_regression --help"
# stg_buildid.sh: STG_URL unset -> exit 3
cat > "projects/$SLUG/.secrets/server.env" <<EOF
SERVER_URL=http://localhost:59999
EOF
./scripts/stg_buildid.sh "$SLUG" >/dev/null 2>&1; [[ $? -eq 3 ]] && ok "stg_buildid exits 3 when STG_URL unset" || no "stg_buildid STG_URL gate"
# stg_buildid.sh: ancestor gate (--offline, no curl)
GATE_REPO="projects/$SLUG/.gate-git"
rm -rf "$GATE_REPO"
mkdir -p "$GATE_REPO"
git -C "$GATE_REPO" init -q
git -C "$GATE_REPO" config user.email "gate@test"
git -C "$GATE_REPO" config user.name "gate"
echo a > "$GATE_REPO/a.txt"; git -C "$GATE_REPO" add a.txt; git -C "$GATE_REPO" commit -q -m "a"
SHA_A=$(git -C "$GATE_REPO" rev-parse --short HEAD)
echo b > "$GATE_REPO/b.txt"; git -C "$GATE_REPO" add b.txt; git -C "$GATE_REPO" commit -q -m "b"
SHA_B=$(git -C "$GATE_REPO" rev-parse --short HEAD)
cat > "projects/$SLUG/.secrets/server.env" <<EOF
SERVER_URL=http://localhost:59999
STG_URL=http://stg.example.invalid
SERVER_GIT_WORKTREE=$ROOT/$GATE_REPO
EOF
OUT=$(./scripts/stg_buildid.sh "$SLUG" "$SHA_A" --offline "$SHA_A" 2>&1); EC=$?
echo "$OUT" | grep -q '^MATCH ' && [[ $EC -eq 0 ]] && ok "stg_buildid MATCH exact" || no "stg_buildid MATCH exact (got: $OUT ec=$EC)"
OUT=$(./scripts/stg_buildid.sh "$SLUG" "$SHA_A" --offline "$SHA_B" 2>&1); EC=$?
echo "$OUT" | grep -q '^MATCH_AHEAD ' && [[ $EC -eq 0 ]] && ok "stg_buildid MATCH_AHEAD ancestor" || no "stg_buildid MATCH_AHEAD (got: $OUT ec=$EC)"
OUT=$(./scripts/stg_buildid.sh "$SLUG" "$SHA_B" --offline "$SHA_A" 2>&1); EC=$?
echo "$OUT" | grep -q '^MISMATCH_BEHIND ' && [[ $EC -eq 2 ]] && ok "stg_buildid MISMATCH_BEHIND" || no "stg_buildid MISMATCH_BEHIND (got: $OUT ec=$EC)"
# rule + skills carry the L5 auto policy
grep_ok "L5 unattended" ".cursor/rules/qa-engine.mdc" "qa-engine has L5 unattended policy"
grep_ok "STG buildId gate" ".cursor/rules/qa-engine.mdc" "qa-engine has STG buildId gate"
grep_ok "Machine DoD for auto-Done" ".cursor/skills/qa-jira/SKILL.md" "qa-jira has machine DoD"
grep_ok "auto-Done" ".cursor/skills/qa-loop/SKILL.md" "qa-loop has auto-Done path"
grep_ok "qa-security" ".cursor/skills/qa-loop/SKILL.md" "qa-loop references qa-security"
grep_ok "exploratory.*regression" ".cursor/skills/qa-security/SKILL.md" "qa-security scoped to exploratory+regression"
grep_ok "Not on every tick" ".cursor/skills/qa-loop/SKILL.md" "qa-loop excludes per-tick security"

echo "== 11b. GitHub CLI gate =="
chmod +x scripts/gh_auth_check.sh 2>/dev/null || true
OUT=$(./scripts/gh_auth_check.sh 2>&1); EC=$?
echo "$OUT" | grep -qiE 'active|inactive' && ok "gh_auth_check prints status (exit $EC)" || no "gh_auth_check output"

echo "== 12. Factory ledger (offline) =="
./scripts/factory_log.sh "$SLUG" _loop tick_start run=selftest-tick >/dev/null
./scripts/factory_log.sh "$SLUG" TST-99 verdict PASS merge_sha=abc123 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-100 verdict FAIL reason=regression >/dev/null
OUT=$(./scripts/factory_status.sh "$SLUG" 2>&1)
echo "$OUT" | grep -q "tickets traced: 2" && ok "factory_status counts tickets" || no "factory_status ticket count"
echo "$OUT" | grep -q "TST-100" && ok "factory_status shows recent activity" || no "factory_status activity"
echo "$OUT" | grep -q "TST-100" && echo "$OUT" | grep -q "failures" && ok "factory_status failure section" || no "factory_status failures"
JSON=$(./scripts/factory_status.sh "$SLUG" --json 2>&1)
echo "$JSON" | grep -q '"ticket_count": 2' && ok "factory_status --json" || no "factory_status json"
[[ -f "projects/$SLUG/factory/runs/_loop.jsonl" ]] && ok "factory _loop.jsonl created" || no "factory log file"

echo "== 12b. Factory tick gate =="
GATE_FAIL=$(./scripts/factory_tick_gate.sh "$SLUG" 2>&1); GATE_EC=$?
echo "$GATE_FAIL" | grep -qi "GATE CLOSED" && ok "factory_tick_gate closed without scope" || no "factory_tick_gate should close without scope"
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-99,TST-100 count=2 >/dev/null
GATE_FAIL2=$(./scripts/factory_tick_gate.sh "$SLUG" 2>&1); GATE_EC2=$?
echo "$GATE_FAIL2" | grep -qi "missing dod_check" && ok "factory_tick_gate requires dod_check" || no "factory_tick_gate dod_check requirement"
./scripts/factory_log.sh "$SLUG" TST-99 handoff_read >/dev/null
./scripts/factory_log.sh "$SLUG" TST-99 dod_check verdict=DONE two_pass=true canonical_source=true buildid_gate=MATCH recording_attached=true feature_steps_executed=true >/dev/null
./scripts/factory_log.sh "$SLUG" TST-100 handoff_read >/dev/null
./scripts/factory_log.sh "$SLUG" TST-100 transition to=In\ Progress reason="env blocked" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-100 dod_check verdict=RETURN_DEV bug_filed=TST-200 transition=In\ Progress openspec_read=true dev_handoff=handoff/TST-100.md retest_attempted=true alternate_locators_tried=true feature_steps_executed=true >/dev/null
./scripts/factory_tick_gate.sh "$SLUG" >/dev/null && ok "factory_tick_gate opens with terminal dod_check" || no "factory_tick_gate should open"
./scripts/factory_log.sh "$SLUG" TST-102 dod_check verdict=BLOCKED bug_filed=TST-201 blocker_note="legacy" >/dev/null 2>&1 || true
GATE_FAIL4=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-102 2>&1)
echo "$GATE_FAIL4" | grep -qi "BLOCKED" && ok "factory_tick_gate rejects BLOCKED" || no "factory_tick_gate should reject BLOCKED"
./scripts/factory_log.sh "$SLUG" TST-101 dod_check verdict=PARTIAL note="incomplete" >/dev/null 2>&1 || true
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-101 count=1 >/dev/null
GATE_FAIL3=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-101 2>&1)
echo "$GATE_FAIL3" | grep -qi "PARTIAL" && ok "factory_tick_gate rejects PARTIAL" || no "factory_tick_gate should reject PARTIAL"

echo "== 12. Usage accounting =="
have scripts/collect_usage.py
have .cursor/skills/usage-accounting/SKILL.md
have .cursor/rules/usage-accounting.mdc
grep_ok "alwaysApply: true" .cursor/rules/usage-accounting.mdc "usage-accounting rule is always-on"
mkdir -p "projects/$SLUG/factory/runs"
./scripts/factory_log.sh "$SLUG" _loop tick_end run=selftest >/dev/null
OUT=$(python3 scripts/collect_usage.py --slug "$SLUG" --days 7 --offline 2>&1)
echo "$OUT" | grep -q "Usage report" && ok "collect_usage prints summary" || no "collect_usage summary"
[[ -f "projects/$SLUG/factory/usage.json" ]] && ok "usage.json written" || no "usage.json missing"
python3 -c "import json; d=json.load(open('projects/$SLUG/factory/usage.json')); assert d['methodology_version']; assert 'A_exact' in d['tiers']; assert 'D_estimated' in d['tiers']" && ok "usage.json schema valid" || no "usage.json schema"

echo "== 13. Jira handoff + transitions (offline) =="
have scripts/jira_handoff.sh
have scripts/jira_handoff.py
have scripts/jira_close_issue.py
have scripts/jira_return_in_progress.py
OUT=$(python3 scripts/jira_handoff.py --project "projects/$SLUG" --key TST-1 2>&1)
echo "$OUT" | grep -qiE 'skipping|no-op|not configured' && ok "jira_handoff no-op when unconfigured" || no "jira_handoff gating (got: $OUT)"
OUT=$(python3 scripts/jira_close_issue.py --project "projects/$SLUG" --key TST-1 --comment "selftest close" 2>&1)
echo "$OUT" | grep -qiE 'skipping|no-op|not configured' && ok "jira_close_issue no-op when unconfigured" || no "jira_close_issue gating"
OUT=$(python3 scripts/jira_return_in_progress.py --project "projects/$SLUG" --key TST-1 --reason "blocked" --steps-tried "step 1" 2>&1)
echo "$OUT" | grep -qiE 'skipping|no-op|not configured' && ok "jira_return_in_progress no-op when unconfigured" || no "jira_return_in_progress gating"
./scripts/jira_handoff.sh "$SLUG" TST-50 --log >/dev/null 2>&1
[[ ! -f "projects/$SLUG/factory/runs/TST-50.jsonl" ]] && ok "jira_handoff --log skips ledger when Jira inactive" || no "jira_handoff must not log without Jira"
cat > "projects/$SLUG/.secrets/jira.env" <<EOF
JIRA_BASE_URL=https://test-co.atlassian.net
JIRA_EMAIL=qa@test-co.io
JIRA_API_TOKEN=tok_realish_123
JIRA_PROJECT_KEY=TST
EOF
DRY=$(python3 scripts/jira_close_issue.py --project "projects/$SLUG" --key TST-1 --comment "done" --dry-run 2>&1)
echo "$DRY" | grep -q 'dry-run' && ok "jira_close_issue dry-run" || no "jira_close_issue dry-run"
DRY=$(python3 scripts/jira_return_in_progress.py --project "projects/$SLUG" --key TST-1 --reason "locator gap" --steps-tried "- tried role=button" --dry-run 2>&1)
echo "$DRY" | grep -q 'dry-run' && ok "jira_return_in_progress dry-run" || no "jira_return_in_progress dry-run"

echo "== 14. OpenSpec coverage gate =="
have scripts/openspec_coverage_gate.py
have scripts/openspec_read.sh
mkdir -p "projects/$SLUG/requirements"
printf '| REQ-AUTH-001 | login |\n| REQ-AUTH-002 | logout |\n| REQ-AUTH-003 | session |\n' > "projects/$SLUG/requirements/openspec-requirements.md"
OS_RUN="projects/$SLUG/runs/2026-07-01-full-selftest"
mkdir -p "$OS_RUN"
printf '| REQ-AUTH-001 | SC | TC | manual | pass | notes | ✅ Pass |\n| REQ-AUTH-002 | SC | TC | manual | pass | notes | Gap — not run |\n| REQ-AUTH-003 | SC | TC | manual | pass | notes | ✅ Pass |\n' > "$OS_RUN/traceability-matrix.md"
python3 scripts/openspec_coverage_gate.py "projects/$SLUG" --matrix "$OS_RUN/traceability-matrix.md" --min 0.90 >/dev/null 2>&1; [[ $? -ne 0 ]] && ok "openspec gate fails below 90%" || no "openspec gate should fail below threshold"
python3 scripts/openspec_coverage_gate.py "projects/$SLUG" --matrix "$OS_RUN/traceability-matrix.md" --min 0.65 >/dev/null 2>&1 && ok "openspec gate opens at 65%" || no "openspec gate should pass at 65%"
printf '| REQ-AUTH-001 | SC | TC | manual | pass | notes | ✅ Pass |\n| REQ-AUTH-002 | SC | TC | manual | pass | notes | ✅ Pass |\n| REQ-AUTH-003 | SC | TC | manual | pass | notes | ✅ Pass |\n' > "$OS_RUN/traceability-matrix.md"
python3 scripts/openspec_coverage_gate.py "projects/$SLUG" --matrix "$OS_RUN/traceability-matrix.md" --min 0.90 >/dev/null 2>&1 && ok "openspec gate passes at 90% with full matrix" || no "openspec gate 90% pass"
OS_LATEST="projects/$SLUG/runs/2099-01-01-full-latest-matrix"
mkdir -p "$OS_LATEST"
cp "$OS_RUN/traceability-matrix.md" "$OS_LATEST/traceability-matrix.md"
python3 scripts/openspec_coverage_gate.py "projects/$SLUG" --min 0.90 >/dev/null 2>&1 && ok "openspec gate finds latest matrix" || no "openspec gate latest matrix"

echo "== 15. OpenSpec read (offline fixture) =="
OSWT="projects/$SLUG/.openspec-fixture"
rm -rf "$OSWT"
mkdir -p "$OSWT/openspec/specs/auth"
printf '# Auth capability\n\nWHEN user logs in THEN dashboard loads.\n' > "$OSWT/openspec/specs/auth/spec.md"
cat > "projects/$SLUG/.secrets/server.env" <<EOF
SERVER_URL=http://localhost:59999
SERVER_GIT_WORKTREE=$ROOT/$OSWT
EOF
OUT=$(./scripts/openspec_read.sh "$SLUG" --cap auth 2>&1)
echo "$OUT" | grep -qi "Auth capability" && ok "openspec_read prints spec excerpt" || no "openspec_read output"
echo "$OUT" | grep -q "openspec/specs/auth/spec.md" && ok "openspec_read cites spec path" || no "openspec_read path"

echo "== 16. Test-data scripts (offline gating) =="
have scripts/test_data_prep.sh
have scripts/test_data_cleanup.sh
OUT=$(./scripts/test_data_prep.sh "$SLUG" 2>&1); EC=$?
echo "$OUT" | grep -qi "Prep spec not found" && [[ $EC -ne 0 ]] && ok "test_data_prep requires project spec" || no "test_data_prep should refuse missing spec"
OUT=$(./scripts/test_data_cleanup.sh "$SLUG" 2>&1); EC=$?
echo "$OUT" | grep -qi "Cleanup spec not found" && [[ $EC -ne 0 ]] && ok "test_data_cleanup requires project spec" || no "test_data_cleanup should refuse missing spec"

echo "== 17. Factory tick gate — FAIL and SKIP_DEV =="
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-extra >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-200 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-200 handoff_read >/dev/null
./scripts/factory_log.sh "$SLUG" TST-200 transition to=In\ Progress reason=regression >/dev/null
./scripts/factory_log.sh "$SLUG" TST-200 dod_check verdict=FAIL reason=regression bug_filed=TST-300 openspec_read=true dev_handoff=handoff/TST-200.md retest_attempted=true feature_steps_executed=true two_pass=true transition=In\ Progress >/dev/null
./scripts/factory_tick_gate.sh "$SLUG" --keys TST-200 >/dev/null && ok "factory_tick_gate accepts FAIL with full DoD" || no "factory_tick_gate FAIL terminal"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-skip-ok >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-201 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-201 handoff_read >/dev/null
./scripts/factory_log.sh "$SLUG" TST-201 dod_check verdict=SKIP_DEV note="dev still coding" jira_status=In\ Progress >/dev/null
./scripts/factory_tick_gate.sh "$SLUG" --keys TST-201 >/dev/null && ok "factory_tick_gate accepts SKIP_DEV in progress" || no "factory_tick_gate SKIP_DEV"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-skip-bad >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-202 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-202 handoff_read >/dev/null
./scripts/factory_log.sh "$SLUG" TST-202 dod_check verdict=SKIP_DEV note="wrong status" jira_status=Validate/Testing >/dev/null
GATE_SKIP2=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-202 2>&1)
echo "$GATE_SKIP2" | grep -qi "SKIP_DEV" && ok "factory_tick_gate rejects SKIP_DEV outside In Progress" || no "factory_tick_gate SKIP_DEV status guard"

echo "== 18. Code review gate =="
have scripts/review_gate.py
have scripts/check_review_gate.sh
have scripts/check_review_gate_fixtures.sh
have scripts/pre_merge_check.sh
have .cursor/rules/code-review.mdc
have .cursor/skills/qa-code-review/SKILL.md
have .github/workflows/code-review.yml
have .github/pull_request_template.md
grep_ok "Blocking issues" .cursor/rules/code-review.mdc "code-review rule has blocking section contract"
grep_ok "check_review_gate" .cursor/rules/code-review.mdc "code-review rule references gate script"
chmod +x scripts/check_review_gate.sh scripts/check_review_gate_fixtures.sh scripts/pre_merge_check.sh scripts/run_code_review.sh 2>/dev/null || true
./scripts/check_review_gate.sh tests/fixtures/review-gate/lgtm.md >/dev/null && ok "review gate passes LGTM fixture" || no "review gate LGTM"
./scripts/check_review_gate.sh tests/fixtures/review-gate/blocking-items.md >/dev/null 2>&1; [[ $? -ne 0 ]] && ok "review gate fails on blockers" || no "review gate should fail blockers"
./scripts/check_review_gate_fixtures.sh && ok "review gate fixtures" || no "review gate fixtures"
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('review_gate', 'scripts/review_gate.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert mod.is_lgtm_only('LGTM - no blocking issues found.')
assert not mod.review_has_blockers('LGTM - no blocking issues found.')
text = open('tests/fixtures/review-gate/blocking-items.md').read()
assert mod.review_has_blockers(text)
assert 'deliveryPipeline' in mod.extract_blocking_section(text)
" && ok "review_gate python unit checks" || no "review_gate python unit checks"
have scripts/cr_autofix.sh
have scripts/fetch_pr_review.sh
have .cursor/rules/cr-autofix.mdc
grep_ok "cr_autofix" .cursor/rules/code-review.mdc "code-review references autofix"
grep_ok "Max 3 attempts" .cursor/rules/cr-autofix.mdc "cr-autofix has attempt cap"
bash scripts/check_review_gate.sh tests/fixtures/review-gate/blocking-items.md >/dev/null 2>&1
OUT=$(bash scripts/cr_autofix.sh --review tests/fixtures/review-gate/blocking-items.md 2>&1); EC=$?
echo "$OUT" | grep -qi "auto-fix" && [[ $EC -ne 0 ]] && ok "cr_autofix requires agent key offline" || no "cr_autofix gating"

echo ""
echo "RESULT: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]

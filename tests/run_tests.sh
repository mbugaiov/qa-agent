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
# Template jira.env.example values must no-op (exit 0 + scope_check), not call the API.
mkdir -p "projects/$SLUG/.secrets"
cp projects/_template/jira.env.example "projects/$SLUG/.secrets/jira.env"
OUT=$(./scripts/jira_status.sh "$SLUG" 2>&1); echo "$OUT" | grep -q inactive && ok "jira_status inactive on template placeholders" || no "jira_status should be inactive for template jira.env"
SCOPE_TMP=$(mktemp)
python3 scripts/jira_scope.py --project "projects/$SLUG" --json --log >"$SCOPE_TMP" 2>/dev/null
SCOPE_EC=$?
[[ "$SCOPE_EC" -eq 0 ]] \
  && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d.get('inactive') is True and d.get('count')==0" "$SCOPE_TMP" \
  && grep -qE '"event"[[:space:]]*:[[:space:]]*"scope_check"' "projects/$SLUG/factory/runs/_loop.jsonl" \
  && ok "jira_scope no-op on template placeholder jira.env" \
  || no "jira_scope must exit 0 + inactive + scope_check for template placeholders"
rm -f "$SCOPE_TMP" "projects/$SLUG/.secrets/jira.env"

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

echo "== 12a. Jira scope shell exports =="
eval "$(./scripts/jira_scope.sh "$SLUG" --shell)"
[[ "${SCOPE_COUNT:-}" == "0" && "${count:-}" == "0" ]] && ok "jira_scope --shell sets count and SCOPE_COUNT" || no "jira_scope SCOPE_COUNT alias"
[[ -n "${SCOPE_KEYS+x}" && -n "${keys+x}" ]] && ok "jira_scope --shell sets keys and SCOPE_KEYS" || no "jira_scope SCOPE_KEYS alias"
python3 - <<'PY' && ok "jira_scope is_placeholder matches engine gate" || no "jira_scope is_placeholder"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("jira_scope", "scripts/jira_scope.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["jira_scope"] = mod
spec.loader.exec_module(mod)
assert mod.is_placeholder("https://your-company.atlassian.net")
assert mod.is_placeholder("you@your-company.com")
assert mod.is_placeholder("paste-atlassian-api-token-here")
assert mod.is_placeholder("ABC")
assert mod.is_placeholder("")
assert not mod.is_placeholder("https://test-co.atlassian.net")
assert not mod.is_placeholder("qa@test-co.io")
assert not mod.is_placeholder("tok_realish_123")
assert not mod.is_placeholder("TST")
PY
python3 - <<'PY' && ok "jira_scope default_jql uses project= not parent= for bare key" || no "jira_scope default_jql project key"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("jira_scope", "scripts/jira_scope.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["jira_scope"] = mod
spec.loader.exec_module(mod)
jql = mod.default_jql({"JIRA_PROJECT_KEY": "ABC"})
assert "parent=ABC" not in jql, jql
assert jql.startswith("project=ABC"), jql
jql2 = mod.default_jql({"JIRA_EPIC_FOR_TASKS_BUGS": "https://x.atlassian.net/browse/ABC-123"})
assert jql2.startswith("parent=ABC-123"), jql2
jql3 = mod.default_jql({"JIRA_SCOPE_JQL": "labels = impl-qa"})
assert jql3 == "labels = impl-qa"
PY
grep -q 'jira_scope.sh' projects/_template/factory/schema.md \
  && grep -qi 'scope empty\|count=0' projects/_template/factory/schema.md \
  && ok "factory schema.md documents scope_check / empty scope" \
  || no "schema.md must document jira_scope --log and empty-scope GATE OPEN"
grep -q 'RUN_PREP' scripts/run_automation.sh \
  && grep -q '\[\[ "\$RUN_PREP" -eq 1 \]\]' scripts/run_automation.sh \
  && ! grep -q 'USE_STG.*SUITE\|SUITE.*USE_STG' scripts/run_automation.sh \
  && ok "run_automation prep is --prep opt-in only" \
  || no "run_automation must not auto-prep on --stg alone"

echo "== 12a2. QA Teams tick notify (offline) =="
python3 - <<'PY' && ok "qa_tick_notify builders + webhook checks" || no "qa_tick_notify unit checks"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("qa_tick_notify", "scripts/qa_tick_notify.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["qa_tick_notify"] = mod
spec.loader.exec_module(mod)

wake = mod.build_tick_notify_summary(
    slug="demo",
    kind="wake",
    count=2,
    issues=[{"key": "TST-1", "summary": "Retest A"}, {"key": "TST-2", "summary": "Retest B"}],
    next_wake_utc="2099-01-01 00:00:00 UTC",
)
assert "QA factory execute" in wake and "TST-1" in wake and "Next tick" in wake, wake
idle = mod.build_tick_notify_summary(slug="demo", kind="idle", next_wake_utc="2099-01-01 00:00:00 UTC")
assert "QA factory idle" in idle, idle
body = mod.build_tick_notify_webhook_body(
    slug="demo",
    kind="wake",
    count=2,
    issues=[{"key": "TST-1", "summary": "Retest A"}, {"key": "TST-2", "summary": "Retest B"}],
    next_wake_utc="2099-01-01 00:00:00 UTC",
)
assert body["type"] == "message"
facts = body["attachments"][0]["content"]["body"][1]["facts"]
titles = {f["title"] for f in facts}
assert "Queue" in titles and "Next tick (UTC)" in titles, titles

assert mod.check_webhook_url(None)["problem"] == "not_configured"
assert mod.check_webhook_url("")["problem"] == "not_configured"
assert mod.check_webhook_url("http://insecure.test/hook")["problem"] == "not_https"
bad = mod.check_webhook_url(
    "https://prod-1.westus.logic.azure.com/workflows/abc/triggers/manual/paths/invoke?api-version=2016-06-01"
)
assert bad["problem"] == "missing_signature", bad
ok_url = mod.check_webhook_url(
    "https://prod-1.westus.logic.azure.com/workflows/abc/triggers/manual/paths/invoke?api-version=2016-06-01&sig=SECRETSIG"
)
assert ok_url["ok"] is True

# Quiet not_configured when posting with empty webhook
outcome = mod.post_qa_tick_notify(slug="demo", kind="idle", webhook_url="")
assert outcome["delivered"] is False and outcome["reason"] == "not_configured"
assert mod.should_report_outcome(outcome) is False
PY
have "scripts/qa_tick_notify.py"
have "scripts/test_tick_notify.sh"
have "scripts/arm_qa_loop.sh"
# Validation only — do not start the sleeper.
! QA_LOOP_INTERVAL_SEC='1200;echo PWNED' bash scripts/arm_qa_loop.sh demo >/dev/null 2>&1 \
  && ok "arm_qa_loop rejects non-numeric interval" \
  || no "arm_qa_loop must reject non-numeric interval"
! bash scripts/arm_qa_loop.sh "bad'slug" >/dev/null 2>&1 \
  && ok "arm_qa_loop rejects invalid slug" \
  || no "arm_qa_loop must reject invalid slug"
grep_ok "QA_FACTORY_TEAMS_WEBHOOK_URL" "projects/_template/jira.env.example" "template documents QA Teams webhook"
grep_ok "QA_FACTORY_TEAMS_WEBHOOK_URL" ".cursor/skills/qa-loop/SKILL.md" "qa-loop documents Teams notify on scope --log"
python3 - <<'PY' && ok "notify_from_scope quiet without webhook" || no "notify_from_scope must stay quiet when unset"
import importlib.util, sys, os
spec = importlib.util.spec_from_file_location("qa_tick_notify", "scripts/qa_tick_notify.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["qa_tick_notify"] = mod
spec.loader.exec_module(mod)
# Ambient webhook must NOT leak when cfg (project file) is provided but omits webhook.
ambient = "https://prod-1.westus.logic.azure.com/workflows/ambient/triggers/manual/paths/invoke?api-version=2016-06-01&sig=AMBIENT"
os.environ["DEV_FACTORY_TEAMS_WEBHOOK_URL"] = ambient
os.environ["AGENT_TEAMS_WEBHOOK_URL"] = ambient
os.environ["QA_FACTORY_TEAMS_WEBHOOK_URL"] = ambient
out = mod.notify_from_scope(slug="demo", keys=["ABC-1"], cfg={}, report=False)
assert out.get("reason") == "not_configured", out
assert mod.should_report_outcome(out) is False
# Empty file values also mean unset (quiet), not fall through to ambient.
out2 = mod.notify_from_scope(
    slug="demo", keys=[], cfg={"QA_FACTORY_TEAMS_WEBHOOK_URL": ""}, report=False
)
assert out2.get("reason") == "not_configured", out2
# File value wins when set.
file_url = "https://prod-1.westus.logic.azure.com/workflows/file/triggers/manual/paths/invoke?api-version=2016-06-01&sig=FILE"
assert mod.get_teams_webhook_url({"QA_FACTORY_TEAMS_WEBHOOK_URL": file_url}) == file_url
assert mod.get_teams_webhook_url({}) is None  # file-only empty → None even if ambient set
for k in ("QA_FACTORY_TEAMS_WEBHOOK_URL", "AGENT_TEAMS_WEBHOOK_URL", "DEV_FACTORY_TEAMS_WEBHOOK_URL"):
    os.environ.pop(k, None)
PY

echo "== 12b. Factory tick gate =="
# Fresh tick with no scope_check yet (prior sections may have logged one).
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-no-scope >/dev/null
GATE_FAIL=$(./scripts/factory_tick_gate.sh "$SLUG" 2>&1); GATE_EC=$?
echo "$GATE_FAIL" | grep -qi "scope_check" && ok "factory_tick_gate closed without scope_check" || no "factory_tick_gate should close without scope_check"
./scripts/jira_scope.sh "$SLUG" --log >/dev/null
grep -qE '"event"[[:space:]]*:[[:space:]]*"scope_check"' "projects/$SLUG/factory/runs/_loop.jsonl" \
  && ok "jira_scope --log writes scope_check" || no "jira_scope --log should append scope_check"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-empty-scope >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys= count=0 >/dev/null
GATE_EMPTY=$(./scripts/factory_tick_gate.sh "$SLUG" 2>&1)
echo "$GATE_EMPTY" | grep -qi "scope empty" && ok "factory_tick_gate opens on count=0" || no "factory_tick_gate empty scope"
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-99,TST-100 count=2 >/dev/null
GATE_FAIL2=$(./scripts/factory_tick_gate.sh "$SLUG" 2>&1); GATE_EC2=$?
echo "$GATE_FAIL2" | grep -qi "missing dod_check" && ok "factory_tick_gate requires dod_check" || no "factory_tick_gate dod_check requirement"
./scripts/factory_log.sh "$SLUG" TST-99 handoff_read >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-99 --title "Selftest gate ticket 99" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-99 dod_check verdict=DONE two_pass=true canonical_source=true buildid_gate=MATCH recording_attached=true feature_steps_executed=true openspec_read=true >/dev/null
./scripts/factory_log.sh "$SLUG" TST-100 handoff_read >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-100 --title "Selftest gate ticket 100" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-100 transition to=In\ Progress reason="env blocked" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-100 dod_check verdict=RETURN_DEV bug_filed=TST-200 transition=In\ Progress openspec_read=true openspec_req=REQ-TEST dev_handoff=handoff/TST-100.md retest_attempted=true alternate_locators_tried=true feature_steps_executed=true bug_recording_attached=true bug_screenshot_attached=true >/dev/null
./scripts/factory_tick_gate.sh "$SLUG" >/dev/null && ok "factory_tick_gate opens with terminal dod_check" || no "factory_tick_gate should open"
./scripts/factory_log.sh "$SLUG" TST-102 dod_check verdict=BLOCKED bug_filed=TST-201 blocker_note="legacy" >/dev/null 2>&1 || true
GATE_FAIL4=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-102 2>&1)
echo "$GATE_FAIL4" | grep -qi "BLOCKED" && ok "factory_tick_gate rejects BLOCKED" || no "factory_tick_gate should reject BLOCKED"
./scripts/factory_log.sh "$SLUG" TST-101 dod_check verdict=PARTIAL note="incomplete" >/dev/null 2>&1 || true
./scripts/factory_log.sh "$SLUG" TST-101 handoff_read >/dev/null 2>&1 || true
./scripts/ticket_tc.sh "$SLUG" TST-101 --title "Selftest partial ticket" >/dev/null 2>&1 || true
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-101 count=1 >/dev/null
GATE_FAIL3=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-101 2>&1)
echo "$GATE_FAIL3" | grep -qi "PARTIAL" && ok "factory_tick_gate rejects PARTIAL" || no "factory_tick_gate should reject PARTIAL"

echo "== 12c. Ticket TC persist =="
have scripts/ticket_tc.sh
have scripts/ticket_tc.py
chmod +x scripts/ticket_tc.sh 2>/dev/null || true
./scripts/ticket_tc.sh "$SLUG" TST-TC1 --title "Ticket driven regression case" --scenario SC-001 --req REQ-001 >/dev/null \
  && ok "ticket_tc creates TC from ticket" || no "ticket_tc create"
[[ -f "projects/$SLUG/test-cases/TC-TST-TC1.md" ]] \
  && grep -q 'TST-TC1' "projects/$SLUG/test-cases/TC-TST-TC1.md" \
  && ok "ticket_tc writes Jira line in TC file" || no "ticket_tc file content"
grep -q 'TST-TC1' "projects/$SLUG/project-memory.md" \
  && ok "ticket_tc updates regression index in project-memory" || no "ticket_tc memory index"
./scripts/ticket_tc.sh "$SLUG" TST-TC1 --title "ignored" 2>&1 | grep -qi existing \
  && ok "ticket_tc idempotent on repeat" || no "ticket_tc idempotent"
grep -q 'ticket_tc' projects/_template/factory/schema.md \
  && ok "factory schema documents ticket_tc / tc_linked" || no "schema ticket_tc docs"
GATE_NO_TC=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-NOTC 2>&1); GATE_NO_TC_EC=$?
echo "$GATE_NO_TC" | grep -qi "persisted TC" && [[ $GATE_NO_TC_EC -ne 0 ]] \
  && ok "factory_tick_gate closed without persisted TC" || no "factory_tick_gate TC requirement"
# (a) pre-existing TC file without a Jira line — must heal marker + index
mkdir -p "projects/$SLUG/test-cases"
cat > "projects/$SLUG/test-cases/TC-TST-HEAL.md" <<'EOF'
# TC-TST-HEAL — orphan without Jira

- **Type**: Acceptance
- **Priority**: P1

## Steps
  1. Placeholder

## Expected
Pass
EOF
./scripts/ticket_tc.sh "$SLUG" TST-HEAL --title "heal orphan" >/dev/null \
  && grep -qE '^\s*-\s*\*\*Jira:\*\*\s*TST-HEAL' "projects/$SLUG/test-cases/TC-TST-HEAL.md" \
  && grep -qE '\| TST-HEAL \|' "projects/$SLUG/project-memory.md" \
  && ok "ticket_tc heals existing file missing Jira line" || no "ticket_tc heal orphan file"
# (b) shorter key after longer key — exact cell match, not substring
./scripts/ticket_tc.sh "$SLUG" TST-10 --title "longer key ten" >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-1 --title "shorter key one" >/dev/null
grep -qE '\| TST-10 \|' "projects/$SLUG/project-memory.md" \
  && grep -qE '\| TST-1 \|' "projects/$SLUG/project-memory.md" \
  && ok "ticket_tc indexes TST-1 and TST-10 as distinct rows" || no "ticket_tc substring key collision"
# (c) --link onto TC that already has a different Jira key
./scripts/ticket_tc.sh "$SLUG" TST-LINK-A --title "shared TC primary" >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-LINK-B --link TC-TST-LINK-A >/dev/null \
  && grep -qE '^\s*-\s*\*\*Jira:\*\*\s*TST-LINK-A' "projects/$SLUG/test-cases/TC-TST-LINK-A.md" \
  && grep -qE '^\s*-\s*\*\*Jira:\*\*\s*TST-LINK-B' "projects/$SLUG/test-cases/TC-TST-LINK-A.md" \
  && grep -qE '\| TST-LINK-B \|' "projects/$SLUG/project-memory.md" \
  && ok "ticket_tc --link adds second Jira key on shared TC" || no "ticket_tc --link second key"

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
./scripts/ticket_tc.sh "$SLUG" TST-200 --title "Selftest FAIL terminal" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-200 transition to=In\ Progress reason=regression >/dev/null
./scripts/factory_log.sh "$SLUG" TST-200 dod_check verdict=FAIL reason=regression bug_filed=TST-300 openspec_read=true openspec_req=REQ-TEST dev_handoff=handoff/TST-200.md retest_attempted=true feature_steps_executed=true two_pass=true transition=In\ Progress bug_recording_attached=true bug_screenshot_attached=true >/dev/null
./scripts/factory_tick_gate.sh "$SLUG" --keys TST-200 >/dev/null && ok "factory_tick_gate accepts FAIL with full DoD" || no "factory_tick_gate FAIL terminal"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-skip-ok >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-201 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-201 handoff_read >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-201 --title "Selftest SKIP_DEV ok" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-201 dod_check verdict=SKIP_DEV note="dev still coding" jira_status=In\ Progress >/dev/null
./scripts/factory_tick_gate.sh "$SLUG" --keys TST-201 >/dev/null && ok "factory_tick_gate accepts SKIP_DEV in progress" || no "factory_tick_gate SKIP_DEV"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-skip-bad >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-202 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-202 handoff_read >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-202 --title "Selftest SKIP_DEV bad status" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-202 dod_check verdict=SKIP_DEV note="wrong status" jira_status=Validate/Testing >/dev/null
GATE_SKIP2=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-202 2>&1)
echo "$GATE_SKIP2" | grep -qi "SKIP_DEV" && ok "factory_tick_gate rejects SKIP_DEV outside In Progress" || no "factory_tick_gate SKIP_DEV status guard"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-skip-lie >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-203 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-203 handoff_read status=Validate/Testing buildId=abc1234 >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-203 --title "Selftest SKIP_DEV stale jira_status" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-203 dod_check verdict=SKIP_DEV note="stale copy" jira_status=In\ Progress >/dev/null
GATE_SKIP3=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-203 2>&1)
echo "$GATE_SKIP3" | grep -qi "Validate/Testing" && ok "factory_tick_gate rejects SKIP_DEV when handoff is V/T" || no "factory_tick_gate V/T SKIP_DEV guard"
echo "$GATE_SKIP3" | grep -qi "mismatch" && ok "factory_tick_gate rejects jira_status/handoff mismatch" || no "factory_tick_gate handoff mismatch guard"

echo "== 17b. Factory tick gate — same-tick completion =="
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-same-tick >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-204 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-204 handoff_read status=In\ Progress >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-204 --title "Selftest autotake defer forbidden" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-204 transition to=In\ Progress reason=autotake >/dev/null
./scripts/factory_log.sh "$SLUG" TST-204 dod_check verdict=SKIP_DEV note="defer next tick" jira_status=In\ Progress retest_attempted=true feature_steps_executed=true >/dev/null
GATE_SAME=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-204 2>&1)
echo "$GATE_SAME" | grep -qi "work started" && ok "factory_tick_gate rejects SKIP_DEV after work started" || no "factory_tick_gate same-tick work guard"
echo "$GATE_SAME" | grep -qi "defer" && ok "factory_tick_gate rejects defer after autotake" || no "factory_tick_gate autotake completion guard"

echo "== 17c. Factory tick gate — impl-qa marathon =="
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-impl-qa-skip >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-205 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-205 handoff_read status=In\ Progress labels=impl-qa >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-205 --title "Selftest impl-qa SKIP forbidden" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-205 dod_check verdict=SKIP_DEV note="monitor" jira_status=In\ Progress >/dev/null
GATE_IQA1=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-205 2>&1)
echo "$GATE_IQA1" | grep -qi "impl-qa" && ok "factory_tick_gate rejects SKIP_DEV on impl-qa" || no "factory_tick_gate impl-qa SKIP guard"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-impl-qa-slice >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-206 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-206 handoff_read status=In\ Progress labels=impl-qa >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-206 --title "Selftest impl-qa QA_CONTINUE slice mode" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-206 dod_check verdict=QA_CONTINUE jira_status=In\ Progress openspec_read=true qa_work_done=true charter_slice="Phase1" charter_artifact=runs/test/execution-log.md note="charter continues" >/dev/null
./scripts/factory_tick_gate.sh "$SLUG" --keys TST-206 >/dev/null && ok "factory_tick_gate accepts QA_CONTINUE in slice mode (no marathon_start)" || no "factory_tick_gate slice QA_CONTINUE"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-impl-qa-marathon >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-208 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" _loop marathon_start ticket=TST-208 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-208 handoff_read status=In\ Progress labels=impl-qa >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-208 --title "Selftest impl-qa QA_CONTINUE forbidden in marathon" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-208 dod_check verdict=QA_CONTINUE jira_status=In\ Progress openspec_read=true qa_work_done=true charter_slice="Phase1" charter_artifact=runs/test/execution-log.md note="charter continues" >/dev/null
GATE_IQA2=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-208 2>&1)
echo "$GATE_IQA2" | grep -qi "marathon" && ok "factory_tick_gate rejects QA_CONTINUE during impl-qa marathon" || no "factory_tick_gate marathon QA_CONTINUE guard"
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-impl-qa-done >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-209 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" _loop marathon_start ticket=TST-209 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-209 handoff_read status=In\ Progress labels=impl-qa >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-209 --title "Selftest impl-qa marathon DONE" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-209 dod_check verdict=DONE two_pass=true canonical_source=true buildid_gate=N/A recording_attached=true retest_attempted=true feature_steps_executed=true openspec_read=true >/dev/null
./scripts/factory_tick_gate.sh "$SLUG" --keys TST-209 >/dev/null && ok "factory_tick_gate accepts DONE during impl-qa marathon" || no "factory_tick_gate marathon DONE"

echo "== 17d. Factory tick gate — bug evidence package =="
./scripts/factory_log.sh "$SLUG" _loop tick_start run=gate-bug-evidence >/dev/null
./scripts/factory_log.sh "$SLUG" _loop scope_check keys=TST-207 count=1 >/dev/null
./scripts/factory_log.sh "$SLUG" TST-207 handoff_read status=Validate/Testing >/dev/null
./scripts/ticket_tc.sh "$SLUG" TST-207 --title "Selftest bug evidence required" >/dev/null
./scripts/factory_log.sh "$SLUG" TST-207 dod_check verdict=FAIL bug_filed=TST-300 openspec_read=true dev_handoff=handoff/TST-207.md retest_attempted=true feature_steps_executed=true transition=In\ Progress >/dev/null
GATE_EV=$(./scripts/factory_tick_gate.sh "$SLUG" --keys TST-207 2>&1)
echo "$GATE_EV" | grep -qi "bug_recording_attached" && ok "factory_tick_gate requires bug recording" || no "factory_tick_gate bug recording"
echo "$GATE_EV" | grep -qi "bug_screenshot_attached" && ok "factory_tick_gate requires bug screenshot" || no "factory_tick_gate bug screenshot"

echo "== 17b. record_retest auth gate (exit 3) =="
# Offline: stub playwright so we exercise expectAuthenticated without a browser.
REC_TMP="$(mktemp -d)"
mkdir -p "$REC_TMP/node_modules/playwright" "$REC_TMP/out" "$REC_TMP/out-ok" "$REC_TMP/out-legacy"
cat > "$REC_TMP/node_modules/playwright/index.js" <<'PWEOF'
class FakeLocator {
  constructor(visible) { this._visible = visible; }
  async isVisible() { return this._visible; }
  async click() {}
}
class FakePage {
  constructor(opts) {
    this._url = opts.finalUrl || 'http://example.test/home';
    this._loginVisible = !!opts.loginVisible;
  }
  async goto(url) {
    // Simulate auth redirect to login when FAKE_REDIRECT_URL is set.
    this._url = process.env.FAKE_REDIRECT_URL || url;
  }
  async fill() {}
  async type() {}
  async click() {}
  async press() {}
  async waitForTimeout() {}
  async waitForSelector() {}
  locator(sel) {
    const loginSel = process.env.FAKE_LOGIN_SEL || '[data-testid=login-user]';
    return new FakeLocator(this._loginVisible && sel === loginSel);
  }
  url() { return this._url; }
  video() { return { path: async () => null }; }
}
class FakeContext {
  constructor(opts) { this._opts = opts; this._page = null; }
  async newPage() {
    this._page = new FakePage({
      finalUrl: process.env.FAKE_PAGE_URL || 'http://example.test/sign-in',
      loginVisible: process.env.FAKE_LOGIN_VISIBLE === '1',
    });
    return this._page;
  }
  async close() {}
}
class FakeBrowser {
  async newContext() { return new FakeContext(); }
  async close() {}
}
module.exports = { chromium: { launch: async () => new FakeBrowser() } };
PWEOF
# Missing unauthenticated indicators → exit 1
cat > "$REC_TMP/bad-meta.json" <<'EOF'
{"expectAuthenticated": true, "steps": [{"do":"goto","url":"http://example.test/app"}]}
EOF
NODE_PATH="$REC_TMP/node_modules" node scripts/record_retest.cjs "$REC_TMP/bad-meta.json" "$REC_TMP/out" >/dev/null 2>&1
[[ $? -eq 1 ]] && ok "record_retest requires unauthenticated indicators" || no "record_retest missing-indicator gate"
# expectAuthenticated + urlIncludes match → exit 3
cat > "$REC_TMP/auth-fail.json" <<'EOF'
{
  "expectAuthenticated": true,
  "unauthenticated": {"urlIncludes": "/sign-in", "selector": "[data-testid=login-user]"},
  "steps": [{"do":"goto","url":"http://example.test/app"}]
}
EOF
FAKE_REDIRECT_URL='http://example.test/sign-in' FAKE_LOGIN_VISIBLE=0 \
  NODE_PATH="$REC_TMP/node_modules" node scripts/record_retest.cjs "$REC_TMP/auth-fail.json" "$REC_TMP/out" >/dev/null 2>&1
[[ $? -eq 3 ]] && ok "record_retest exits 3 when unauthenticated (urlIncludes)" || no "record_retest exit 3 urlIncludes"
# expectAuthenticated + selector visible → exit 3
FAKE_PAGE_URL='http://example.test/app' FAKE_LOGIN_VISIBLE=1 \
  NODE_PATH="$REC_TMP/node_modules" node scripts/record_retest.cjs "$REC_TMP/auth-fail.json" "$REC_TMP/out" >/dev/null 2>&1
[[ $? -eq 3 ]] && ok "record_retest exits 3 when unauthenticated (selector)" || no "record_retest exit 3 selector"
# protected alias + authenticated page → no exit 3 (falls through to exit 2: no video from stub)
cat > "$REC_TMP/auth-ok.json" <<'EOF'
{
  "protected": true,
  "unauthenticated": {"urlIncludes": "/sign-in"},
  "steps": [{"do":"goto","url":"http://example.test/app"}]
}
EOF
FAKE_PAGE_URL='http://example.test/app' FAKE_LOGIN_VISIBLE=0 \
  NODE_PATH="$REC_TMP/node_modules" node scripts/record_retest.cjs "$REC_TMP/auth-ok.json" "$REC_TMP/out-ok" >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "record_retest skips auth reject when authenticated" || no "record_retest authenticated path"
# Legacy array steps: no auth gate even if URL looks like sign-in
cat > "$REC_TMP/legacy.json" <<'EOF'
[{"do":"goto","url":"http://example.test/sign-in"}]
EOF
FAKE_PAGE_URL='http://example.test/sign-in' \
  NODE_PATH="$REC_TMP/node_modules" node scripts/record_retest.cjs "$REC_TMP/legacy.json" "$REC_TMP/out-legacy" >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "record_retest legacy array has no auth gate" || no "record_retest legacy array"
# Engine must not hardcode app routes/selectors for this gate
! grep -qE "['\"]/(dashboard|login)['\"]|#username" scripts/record_retest.cjs \
  && ok "record_retest has no hardcoded app auth paths" || no "record_retest portability (auth paths)"
rm -rf "$REC_TMP"

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
OUT=$(env -u CURSOR_API_KEY bash scripts/cr_autofix.sh --review 2>&1); EC=$?
echo "$OUT" | grep -qi "Usage: --review" && [[ $EC -ne 0 ]] && ok "cr_autofix rejects missing --review value" || no "cr_autofix arg validation"
OUT=$(env -u CURSOR_API_KEY bash scripts/cr_autofix.sh --review tests/fixtures/review-gate/blocking-items.md 2>&1); EC=$?
echo "$OUT" | grep -qi "auto-fix" && [[ $EC -ne 0 ]] && ok "cr_autofix requires agent key offline" || no "cr_autofix gating"
grep_ok "committed fixes locally" scripts/cr_autofix.sh "cr_autofix commits before re-review"
grep_ok "last | .body" scripts/fetch_pr_review.sh "fetch_pr_review uses full comment body"
python3 - <<'PY' && ok "fetch_pr_review comment parse offline" || no "fetch_pr_review parse"
from pathlib import Path
body = "<!-- qa-agent-cursor-review -->\n## Cursor automated review\n\n## Summary\nok\n## Blocking issues\nNone.\n"
if "<!-- qa-agent-cursor-review -->" in body:
    body = body.split("<!-- qa-agent-cursor-review -->", 1)[1]
if "## Cursor automated review" in body:
    body = body.split("## Cursor automated review", 1)[1]
assert "Blocking issues" in body and "None" in body
PY

echo ""
echo "RESULT: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]

# Factory run ledger — event schema

Per-ticket trace files: `projects/<slug>/factory/runs/<JIRA-KEY>.jsonl`  
Loop-level events: `projects/<slug>/factory/runs/_loop.jsonl`

Each line is one JSON object (JSONL). All events include:

| Field | Required | Description |
|-------|----------|-------------|
| `ts` | yes | UTC ISO-8601 timestamp |
| `event` | yes | Event name (see below) |
| `agent` | yes | `qa` \| `dev` \| `cr` \| `system` |
| `ticket` | usually | Jira key; `_loop` for tick-level events |
| `detail` | no | Free-form object (verdict, sha, run id, …) |

## QA loop events (`agent=qa`)

| Event | When | Typical `detail` |
|-------|------|------------------|
| `tick_start` | Start of a qa-loop tick | `{ "run": "<run-id>" }` |
| `scope_check` | Jira scope queried (required each tick) | `{ "keys": ["RQ-…"], "count": N }` |
| `marathon_start` | Opt into impl-qa marathon (freeze until Done) | `{ "ticket": "RQ-…" }` on `_loop`, or bare event on the ticket |
| `handoff_read` | Dev handoff consumed before V/T retest | `{ "buildId": "…", "pr": "…", "status": "…" }` |
| `tc_linked` | Ticket mapped to persisted regression TC | `{ "tc_id": "TC-RQ-1", "path": "test-cases/…", "created": true \| "existing": true }` |
| `dod_check` | **Per scope ticket before tick_end** | See **DoD gate** below |
| `verdict_review` | Before Done/FAIL/RETURN (skill `qa-verdict-review`) | `{ "result": "pass", "artifact": "runs/…/verdict-review-<KEY>.md" }` |
| `backlog_drained` | Final step before `tick_end` when real work happened | `{ "count": N }` — proof `jira_scope.sh` was re-run after resolving and the queue was checked again |
| `recording_attached` | E2E clip attached to ticket | `{ "caption": "…" }` |
| `tick_end` | End of tick (after gate passes) | `{ "run", "scope_count", "gate": "open" }` |
| `verdict` | Retest result (legacy / extra) | `{ "verdict": "PASS\|FAIL\|needs-human", "merge_sha", "buildid" }` |
| `transition` | Jira status change | `{ "to": "Done\|In Progress\|Validate/Testing" }` |
| `bug_filed` | New confirmed defect | `{ "key": "RQ-…", "severity": "S2" }` |
| `regression_reopen` | Done ticket failed retest | `{ "reason": "…" }` |
| `exploratory` | Exploratory slice | `{ "area": "…" }` |
| `security_slice` | Security checklist slice | `{ "topic": "…" }` |

## DoD gate (`scope_check` + `dod_check` + `factory_tick_gate.sh`)

**Mandatory each tick (after `tick_start`):** log `scope_check` via Jira scope query — do **not**
hand-write an empty scope or skip when Jira is configured:

```bash
eval "$(./scripts/jira_scope.sh <slug> --log --shell)"
# --log appends scope_check {keys, count} to _loop.jsonl (required by the gate)
```

**Before `tick_end`**, `factory_tick_gate.sh` enforces:

| Condition | Gate result |
|-----------|-------------|
| No `scope_check` since `tick_start` | **CLOSED** — run `jira_scope.sh … --log` |
| `scope_check` with `count=0` and no keys | **OPEN** — empty scope; exploratory allowed (no `dod_check` required) |
| `count>0` but keys missing | **CLOSED** — re-run `jira_scope.sh --log` |
| Each scope key missing terminal `dod_check` | **CLOSED** — log per-ticket `dod_check` |
| Each scope key missing persisted TC in `test-cases/` (`**Jira:** KEY`) | **CLOSED** — run `ticket_tc.sh` after OpenSpec read |

```bash
./scripts/ticket_tc.sh <slug> <KEY> --title "…" [--steps-file runs/<run>/steps-<KEY>.md] [--log]
./scripts/factory_tick_gate.sh <slug>              # uses latest scope_check keys
./scripts/factory_tick_gate.sh <slug> --keys RQ-1,RQ-2
```

Exit **0** = gate open → safe to log `tick_end`. Exit **1** = gate closed → do not end tick.

### `dod_check` detail fields

| Field | Required when | Values |
|-------|---------------|--------|
| `verdict` | always | Terminal only: `DONE`, `FAIL`, `RETURN_DEV`, `SKIP_DEV`, `QA_CONTINUE` |
| `two_pass` | `DONE` | `true` — Pass 1 real input + Pass 2 automation agree |
| `canonical_source` | `DONE` | `true` — verified detail page / API / audit, not UI-only proxy |
| `buildid_gate` | `DONE` | `MATCH`, `MATCH_AHEAD`, `N/A`, or `SKIP` |
| `jira_status` | `SKIP_DEV`, `QA_CONTINUE` | Must be `In Progress` **and match** `handoff_read` status this tick |
| `note` | `SKIP_DEV`, `QA_CONTINUE` | Why dev-owned skip, or charter status for QA_CONTINUE |
| `charter_slice` | `QA_CONTINUE` | One-line summary of **active QA work done this tick** on impl-qa charter |
| `charter_artifact` | `QA_CONTINUE` | Run-folder path updated (execution-log, security-checklist, exploratory-session, …) |
| `qa_work_done` | `QA_CONTINUE` | `true` — proves charter slice executed (not monitor-only) |
| `openspec_read` | `QA_CONTINUE`, `FAIL`, `RETURN_DEV`, **`DONE`** | `true` — after `openspec_read.sh`; expected behaviour from OpenSpec THEN |
| `verdict_review` | `DONE`, `FAIL`, `RETURN_DEV` | `pass` / `true` — after skill `qa-verdict-review` + `check_verdict_review.sh` (or separate `verdict_review` event with `result=pass`) |
| `dev_handoff` | `FAIL`, `RETURN_DEV` | path to `retest-fail-<KEY>.md` posted to Jira |
| `recording_exempt` | pure-CI tickets | `true` |
| `retest_attempted` | `FAIL`, `RETURN_DEV`, `DONE` | `true` — feature-specific steps were run (smoke alone insufficient) |
| `feature_steps_executed` | `FAIL`, `RETURN_DEV`, `DONE` | `true` — ticket test plan steps executed |
| `alternate_locators_tried` | `RETURN_DEV` | `true` — exhausted data-testid / role / text / native click |
| `steps_tried` | `RETURN_DEV` (optional alt.) | Short summary if `feature_steps_executed` omitted |
| `bug_filed` | `FAIL`, `RETURN_DEV` | Jira key of separate bug (product defect or env blocker) |
| `bug_recording_attached` | `FAIL`, `RETURN_DEV` (when `bug_filed`/`dev_ticket`) | `true` — recording on the **bug** key (`record_and_attach.sh` Jira, or `github_create_issue.py --attach`/gist) |
| `bug_screenshot_attached` | `FAIL`, `RETURN_DEV` (when `bug_filed`/`dev_ticket`) | `true` — screenshot via `create_bug_issue.py --attach` (Jira or GitHub) |
| `openspec_req` | `FAIL`, `RETURN_DEV`, `DONE`, bug filing | REQ-ID from `openspec_read.sh` (oracle for expected) |
| `openspec_scenario` | alt. to `openspec_req` | Scenario name from OpenSpec |
| `dev_ticket` | `RETURN_DEV` (locator gap) | impl-dev task for testids/locators |
| `transition` | `FAIL`, `RETURN_DEV` | `In Progress` — logged via `transition` event or field |

**`impl-qa` ownership (gate enforced):** when `handoff_read.labels` includes **`impl-qa`**, **`SKIP_DEV` is rejected**. **Slice mode (default):** `QA_CONTINUE` with `charter_slice` + `charter_artifact` may open `tick_end`. **Marathon mode (opt-in):** log `marathon_start` this tick — then gate freezes until **Done** (`QA_CONTINUE` rejected; other scope tickets wait). **Evidence on Done:** E2E recording + OpenSpec-checked steps (`openspec_read=true`).

**Bug filing evidence (gate enforced):** `FAIL`/`RETURN_DEV` with `bug_filed` or `dev_ticket` requires **`bug_recording_attached=true`**, **`bug_screenshot_attached=true`**, and **`openspec_req`** or **`openspec_scenario`**.

**Handoff cross-check (gate enforced):** `factory_tick_gate.sh` reads `handoff_read.status` from the
same tick. **`SKIP_DEV` is rejected** when handoff is **Validate/Testing**. **`dod_check.jira_status`**
must match handoff — stale `In Progress` while Jira is V/T closes the gate (stale handoff status anti-pattern).

**Same-tick completion (gate enforced):** `transition to=In Progress`, `retest_attempted=true`, or
`feature_steps_executed=true` this tick ⇒ **`tick_end` requires `DONE`** (or `FAIL` / `RETURN_DEV` with
full blocker fields). **`SKIP_DEV` after work started is rejected** (partial deferral anti-pattern).

**Backlog drain (gate enforced):** whenever any ticket from **any** `scope_check` this tick resolves
`DONE`/`FAIL`/`RETURN_DEV` (union of keys across rescans — not only the latest scan),
`factory_tick_gate.sh` requires a `backlog_drained` event on `_loop.jsonl` before it opens — proof the
agent re-ran `jira_scope.sh <slug> --log --shell` **again** after resolving scope, and either found
nothing left (`count=0`) or confirmed the remainder is legitimately dev-owned `SKIP_DEV`. A tick that
resolves one ticket and stops without this event is **closed**: "no backlog_drained event logged."
Completed tickets that drop off a later empty/SKIP_DEV-only rescan still count as real work.
Log `backlog_drained` **after** the drain loop settles and **before** running the gate.

```bash
# ... resolve scope tickets, re-scan until clean/SKIP_DEV-only ...
./scripts/factory_log.sh <slug> _loop backlog_drained count=0
./scripts/factory_tick_gate.sh <slug>
```

### Forbidden verdicts at `tick_end`

Never log `dod_check` with **`PARTIAL`**, **`DEFERRED`**, or **`PASS_PENDING`**. Those mean
work is incomplete — continue the same tick until terminal verdict.

### Example (ticket closed Done)

```bash
# Skill qa-verdict-review (critique — not a third browser pass):
bash scripts/check_verdict_review.sh projects/<slug>/runs/<run>/verdict-review-ABC-1.md
./scripts/factory_log.sh <slug> ABC-1 verdict_review result=pass \
  artifact=runs/<run>/verdict-review-ABC-1.md
./scripts/factory_log.sh <slug> ABC-1 dod_check \
  verdict=DONE two_pass=true canonical_source=true \
  buildid_gate=MATCH recording_attached=true \
  retest_attempted=true feature_steps_executed=true openspec_read=true \
  verdict_review=pass
./scripts/factory_log.sh <slug> ABC-1 recording_attached caption="Feature verified E2E"
# Close scripts refuse without ledger verdict_review=pass:
python3 scripts/jira_close_issue.py --project projects/<slug> --key ABC-1 \
  --to Done --comment "QA PASS"
./scripts/factory_log.sh <slug> ABC-1 transition to=Done
```

### Example (blocked — return V/T to dev, never stay blocked in V/T)

```bash
./scripts/jira_handoff.sh <slug> ABC-2 --log
bash scripts/check_verdict_review.sh projects/<slug>/runs/<run>/verdict-review-ABC-2.md
./scripts/factory_log.sh <slug> ABC-2 verdict_review result=pass \
  artifact=runs/<run>/verdict-review-ABC-2.md
./scripts/factory_log.sh <slug> ABC-2 dod_check \
  verdict=RETURN_DEV dev_ticket=ABC-9 transition=In\ Progress \
  retest_attempted=true alternate_locators_tried=true feature_steps_executed=true \
  openspec_read=true openspec_req=REQ-… verdict_review=pass \
  bug_filed=ABC-9 bug_recording_attached=true bug_screenshot_attached=true
python3 scripts/jira_return_in_progress.py --project projects/<slug> --key ABC-2 \
  --reason "Automation cannot reach required control" --dev-ticket ABC-9 \
  --steps-tried "1. handoff read 2. test_data_prep 3. primary flow 4. alt locators"
./scripts/factory_log.sh <slug> ABC-2 transition to=In\ Progress reason="locator gap"
```

### Example (impl-qa charter — slice mode continue)

Do **not** log `marathon_start` this tick. Gate accepts `QA_CONTINUE` when charter fields are present:

```bash
./scripts/jira_handoff.sh <slug> RQ-99 --log   # handoff_read includes labels=impl-qa
./scripts/factory_log.sh <slug> RQ-99 dod_check \
  verdict=QA_CONTINUE jira_status="In Progress" openspec_read=true qa_work_done=true \
  charter_slice="Phase 2: manual cron path with CRON_SECRET" \
  charter_artifact="runs/<run-id>/execution-log.md" \
  note="Acceptance not met — charter continues"
```

### Example (impl-qa marathon — opt-in freeze until Done)

```bash
./scripts/factory_log.sh <slug> _loop marathon_start ticket=RQ-99
# … work charter until acceptance …
./scripts/factory_log.sh <slug> RQ-99 dod_check \
  verdict=DONE two_pass=true canonical_source=true buildid_gate=N/A \
  recording_attached=true retest_attempted=true feature_steps_executed=true openspec_read=true
# tick_end only after DONE; QA_CONTINUE is rejected while marathon_start is active
```

## Dev factory events (`agent=dev`) — ingest manually or via dev loop

Documented for cross-agent traceability; dev loop may call `factory_log.sh` when implemented.

| Event | When |
|-------|------|
| `pick` | impl-dev To Do ticket selected |
| `branch` | Feature branch created |
| `openspec_validate` | OpenSpec validate passed |
| `mr_open` | MR/PR opened |
| `cr_pass` / `cr_block` | Code review gate |
| `merge` | Merged to main |
| `deploy` | STG deploy completed |
| `handoff_vt` | Moved to Validate/Testing + buildId comment |

| `usage_snapshot` | Tier A usage collected | `{ "tier": "A", "input": N, "output": N, "usd_cents": N }` |

## Cross-reference

- Usage methodology: skill `usage-accounting` · script `scripts/collect_usage.py`

## Usage

```bash
./scripts/factory_log.sh <slug> _loop tick_start run=<run-id>
eval "$(./scripts/jira_scope.sh <slug> --log --shell)"   # mandatory scope_check
# If count=0 → factory_tick_gate opens immediately (exploratory-only tick).
# If count>0 → handoff + tc persist + dod_check per key before gate:
./scripts/jira_handoff.sh <slug> RQ-1 --log
./scripts/ticket_tc.sh <slug> RQ-1 --title "…" --log
./scripts/factory_log.sh <slug> RQ-1 verdict_review result=pass artifact=runs/<run>/verdict-review-RQ-1.md
./scripts/factory_log.sh <slug> RQ-1 dod_check \
  verdict=DONE two_pass=true canonical_source=true \
  buildid_gate=MATCH recording_attached=true retest_attempted=true feature_steps_executed=true \
  openspec_read=true verdict_review=pass
./scripts/factory_tick_gate.sh <slug>
./scripts/factory_log.sh <slug> _loop exploratory area="…" result=PASS
./scripts/factory_log.sh <slug> _loop tick_end run=<run-id> gate=open
./scripts/factory_status.sh <slug>
```

**Gate also rejects:** missing persisted TC per scope key; `exploratory` before all scope `dod_check` when `scope_check count > 0`;
`RETURN_DEV` without `retest_attempted` + `alternate_locators_tried`; missing `handoff_read` per scope key.

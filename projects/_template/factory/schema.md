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
| `handoff_read` | Dev handoff consumed before V/T retest | `{ "buildId": "…", "pr": "…", "status": "…" }` |
| `dod_check` | **Per scope ticket before tick_end** | See **DoD gate** below |
| `recording_attached` | E2E clip attached to ticket | `{ "caption": "…" }` |
| `tick_end` | End of tick (after gate passes) | `{ "run", "scope_count", "gate": "open" }` |
| `verdict` | Retest result (legacy / extra) | `{ "verdict": "PASS\|FAIL\|needs-human", "merge_sha", "buildid" }` |
| `transition` | Jira status change | `{ "to": "Done\|In Progress\|Validate/Testing" }` |
| `bug_filed` | New confirmed defect | `{ "key": "RQ-…", "severity": "S2" }` |
| `regression_reopen` | Done ticket failed retest | `{ "reason": "…" }` |
| `exploratory` | Exploratory slice | `{ "area": "…" }` |
| `security_slice` | Security checklist slice | `{ "topic": "…" }` |

## DoD gate (`dod_check` + `factory_tick_gate.sh`)

**Before `tick_end`**, every scope ticket from the latest `scope_check` must have a `dod_check`
event logged in the **current tick** (since last `tick_start`). Run:

```bash
./scripts/factory_tick_gate.sh <slug>              # uses latest scope_check keys
./scripts/factory_tick_gate.sh <slug> --keys RQ-1,RQ-2
```

Exit **0** = gate open → safe to log `tick_end`. Exit **1** = gate closed → do not end tick.

### `dod_check` detail fields

| Field | Required when | Values |
|-------|---------------|--------|
| `verdict` | always | Terminal only: `DONE`, `FAIL`, `RETURN_DEV`, `SKIP_DEV` |
| `two_pass` | `DONE` | `true` — Pass 1 real input + Pass 2 automation agree |
| `canonical_source` | `DONE` | `true` — verified detail page / API / audit, not UI-only proxy |
| `buildid_gate` | `DONE` | `MATCH`, `MATCH_AHEAD`, `N/A`, or `SKIP` |
| `openspec_read` | `FAIL`, `RETURN_DEV` | `true` — after `openspec_read.sh` |
| `dev_handoff` | `FAIL`, `RETURN_DEV` | path to `retest-fail-<KEY>.md` posted to Jira |
| `recording_exempt` | pure-CI tickets | `true` |
| `retest_attempted` | `FAIL`, `RETURN_DEV`, `DONE` | `true` — feature-specific steps were run (smoke alone insufficient) |
| `feature_steps_executed` | `FAIL`, `RETURN_DEV`, `DONE` | `true` — ticket test plan steps executed |
| `alternate_locators_tried` | `RETURN_DEV` | `true` — exhausted data-testid / role / text / native click |
| `steps_tried` | `RETURN_DEV` (optional alt.) | Short summary if `feature_steps_executed` omitted |
| `bug_filed` | `FAIL`, `RETURN_DEV` | Jira key of separate bug (product defect or env blocker) |
| `dev_ticket` | `RETURN_DEV` (locator gap) | impl-dev task for testids/locators |
| `transition` | `FAIL`, `RETURN_DEV` | `In Progress` — logged via `transition` event or field |
| `jira_status` | `SKIP_DEV` | Must be `In Progress` |
| `note` | `SKIP_DEV` | Why dev-owned — not V/T retest this tick |

### Forbidden verdicts at `tick_end`

Never log `dod_check` with **`PARTIAL`**, **`DEFERRED`**, or **`PASS_PENDING`**. Those mean
work is incomplete — continue the same tick until terminal verdict.

### Example (ticket closed Done)

```bash
./scripts/factory_log.sh <slug> ABC-1 dod_check \
  verdict=DONE two_pass=true canonical_source=true \
  buildid_gate=MATCH recording_attached=true
./scripts/factory_log.sh <slug> ABC-1 recording_attached caption="Feature verified E2E"
./scripts/factory_log.sh <slug> ABC-1 transition to=Done
```

### Example (blocked — return V/T to dev, never stay blocked in V/T)

```bash
./scripts/jira_handoff.sh <slug> ABC-2 --log
python3 scripts/jira_return_in_progress.py --project projects/<slug> --key ABC-2 \
  --reason "Automation cannot reach required control" --dev-ticket ABC-9 \
  --steps-tried "1. handoff read 2. test_data_prep 3. primary flow 4. alt locators"
./scripts/factory_log.sh <slug> ABC-2 transition to=In\ Progress reason="locator gap"
./scripts/factory_log.sh <slug> ABC-2 dod_check \
  verdict=RETURN_DEV dev_ticket=ABC-9 transition=In\ Progress \
  retest_attempted=true alternate_locators_tried=true feature_steps_executed=true
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
./scripts/factory_log.sh <slug> _loop scope_check keys=RQ-1,RQ-2 count=2
./scripts/jira_handoff.sh <slug> RQ-1 --log
./scripts/factory_log.sh <slug> RQ-1 dod_check \
  verdict=DONE two_pass=true canonical_source=true \
  buildid_gate=MATCH recording_attached=true retest_attempted=true feature_steps_executed=true
./scripts/factory_tick_gate.sh <slug>
./scripts/factory_log.sh <slug> _loop exploratory area="…" result=PASS
./scripts/factory_log.sh <slug> _loop tick_end run=<run-id> gate=open
./scripts/factory_status.sh <slug>
```

**Gate also rejects:** `exploratory` before all scope `dod_check` when `scope_check count > 0`;
`RETURN_DEV` without `retest_attempted` + `alternate_locators_tried`; missing `handoff_read` per scope key.

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
| `tick_end` | End of tick (before re-arm) | `{ "run", "scope_count", "verdicts" }` |
| `scope_check` | Jira scope queried | `{ "keys": ["ABC-…"], "count": N }` |
| `verdict` | Retest result | `{ "verdict": "PASS\|FAIL\|needs-human", "merge_sha", "buildid" }` |
| `transition` | Jira status change | `{ "to": "Done\|In Progress\|Validate/Testing" }` |
| `bug_filed` | New confirmed defect | `{ "key": "ABC-…", "severity": "S2" }` |
| `regression_reopen` | Done ticket failed retest | `{ "reason": "…" }` |
| `exploratory` | Exploratory slice | `{ "area": "…" }` |
| `security_slice` | Security checklist slice | `{ "topic": "…" }` |

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

## Usage

```bash
./scripts/factory_log.sh <slug> _loop tick_start run=<YYYY-MM-DD>-exploratory-<task>
./scripts/factory_log.sh <slug> ABC-123 verdict PASS merge_sha=<sha> buildid=MATCH
./scripts/factory_status.sh <slug>
```

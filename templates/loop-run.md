# Run — <task title> (continuous loop)

> Loop engagement manifest. Durable state → `project-memory.md` (active loop, coverage, cadence).

- **Run id**: <YYYY-MM-DD>-exploratory-<task-slug>
- **Type**: exploratory (recurring L5 / continuous QA loop)
- **Date**: <YYYY-MM-DD>
- **Scope**: retest Jira active scope + exploratory on uncovered areas (security: exploratory/regression runs only — skill `qa-security`)
- **Prior run (if rotated):** `runs/<previous-run-id>/` (archived — history preserved)

## Mandate (each tick)
1. Jira scope check first (`scope_check` + factory ledger).
2. **If scope count > 0:** `jira_handoff.sh <slug> <KEY> --log` per ticket **before** browser work.
3. Retest active tickets per machine DoD (`qa-jira` + per-ticket checklist below).
4. **Feature tests needing assign/relocate on STG:** prep → test → cleanup (`qa-test-data` skill).
5. `factory_tick_gate.sh` → gate open.
6. **Only then:** fresh exploratory — rotate toward uncovered areas (`project-memory.md` coverage ledger).
7. Auto-file / auto-reopen per project policy.
8. Append iteration log below; update `project-memory.md` when material state changes.

**Security** is not per tick — run on `exploratory` and `regression` runs (skill `qa-security`).

**Start loop (Agent chat):** `/loop 3600 AGENT_LOOP_WAKE_<purpose>` — see skill `qa-loop` (interval in seconds; not a bash command).

## Per-ticket checklist (copy per scope key each tick)

```
Ticket: <KEY>  Status: <V/T|In Progress>

[ ] handoff_read     — ./scripts/jira_handoff.sh <slug> <KEY> --log
[ ] openspec_read    — ./scripts/openspec_read.sh <slug> --ticket <KEY> (skill qa-openspec)
[ ] test_plan        — 3–5 steps from OpenSpec + handoff (write below)
[ ] buildid_gate     — stg_buildid.sh → MATCH|MATCH_AHEAD
[ ] test_data_prep   — if assign/relocate (else N/A)
[ ] feature_retest   — two-pass on canonical source (NOT smoke-only)
[ ] recording        — record_and_attach.sh (or recording_exempt)
[ ] jira_transition  — Done | In Progress + comment
[ ] dev_handoff      — on FAIL/RETURN_DEV: templates/retest-fail-dev-handoff.md → jira_return_in_progress.py --handoff-file
[ ] dod_check        — terminal verdict logged (FAIL needs openspec_read=true + dev_handoff=<path>)

Test plan:
1. …
2. …
3. …
```

## Iteration log

### Tick 0 — <date> (run opened)
- <why this run was created / rotated from prior run>

## Result
- **Verdict**: in progress
- **Memory updated**: ☐ yes
